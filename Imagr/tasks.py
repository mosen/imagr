import abc
import os
import subprocess
import tempfile
import shutil
import re

import objc
from Foundation import *
from Cocoa import *
import macdisk

import osinstall
import Utils


class ImagrTaskError(Exception):
    pass


class ImagrTaskDelegate(NSObject):

    @abc.abstractmethod
    def updateProgressTitle_Percent_Detail_(self, title, percent, detail):
        pass


class ImagrReportDelegate(NSObject):

    @abc.abstractmethod
    def sendReport(self, status, message):
        pass


class ImagrTask(NSObject):

    progressDelegate = None
    reportDelegate = None
    item = None
    target = None  # type: macdisk.Disk
    _newTarget = None

    def init(self):
        """Designated Initializer for ImagrTask"""
        self = objc.super(ImagrTask, self).init()
        if self is None:
            return None

        return self

    def initWithItem_(self, item):
        """Initialise an ImagrTask with the item dict for this step."""
        self = objc.super(ImagrTask, self).init()
        if self is None:
            return None

        self.item = item

        return self

    def initWithItem_target_(self, item, target):
        """Initialise an ImagrTask with the item dict for this step, and the target volume."""
        self = objc.super(ImagrTask, self).init()
        if self is None:
            return None

        self.item = item
        self.target = target

        return self

    def newTarget(self):  # type: () -> Optional[macdisk.Disk]
        """Target did change as a result of this operation?"""
        return self._newTarget


    @abc.abstractmethod
    def run(self, dry=False):  # type: (bool) -> Union[None, str, List]
        """Run the task.

        Args:
            dry: Enable dry-run, which means that no destructive operations will be performed, they will only be logged
                as they would be performed.

        Returns:
            workflow name or components Union[str, List]: Either the name of a new workflow to run, or a list of components
            that should be run. Return None for no action
        """
        pass

    def is_valid(self, item):
        """Validate the workflow item that the user has configured.

        Args:
            item: The dict containing the specification for this task.

        Returns:
            A 2 element tuple of (bool, None|str) indicating the validity, and a message to be displayed if not valid.
        """
        return True, None

    @classmethod
    def taskForItem_target_(cls, item, target):
        # type: (dict, macdisk.Disk) -> Optional[ImagrTask]
        """Instantiate the correct task instance given a workflow item dict."""
        if 'type' not in item:
            raise TypeError('Workflow component contains no `type` key')

        t = item.get('type')

        if t == 'image':
            task = ImageTask.alloc().initWithItem_target_(item, target)
        elif t == 'startosinstall':
            task = StartOSInstallTask.alloc().initWithItem_target_(item, target)
        elif t == 'partition':
            task = PartitionTask.alloc().initWithItem_target_(item, target)
        elif t == 'package':
            if item.get('first_boot', True):
                task = FirstBootPackageTask.alloc().initWithItem_target_(item, target)
            else:
                task = InstallPackageTask.alloc().initWithItem_target_(item, target)
        elif t == 'reformat':
            task = ReformatTask.alloc().initWithItem_target_(item, target)
        elif t == 'script':
            if item.get('first_boot', True):
                task = FirstBootScriptTask.alloc().initWithItem_target_(item, target)
            else:
                task = ScriptTask.alloc().initWithItem_target_(item, target)
        else:
            raise TypeError("Unexpected task type: %s" % t)

        return task



class IncludedWorkflowTask(ImagrTask):

    def includedWorkflowFromScript(self, script):  # type: (str) -> str
        """Get an included workflow name by running a script provided in the workflow configuration."""
        included_workflow = None

        if self.progressDelegate:
            self.progressDelegate.updateProgressTitle_Percent_Detail_("Running script to determine included workflow...", -1, '')

        script = Utils.replacePlaceholders(self.item.get('script'), self.target.mountpoint)
        script_file = tempfile.NamedTemporaryFile(delete=False)
        script_file.write(script)
        script_file.close()
        os.chmod(script_file.name, 0700)
        proc = subprocess.Popen(script_file.name, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

        while proc.poll() is None:
            output = proc.stdout.readline().strip().decode('UTF-8')

            if output.startswith("ImagrIncludedWorkflow:"):
                included_workflow = output.replace("ImagrIncludedWorkflow:", "").strip()

            if self.progressDelegate:
                self.progressDelegate.updateProgressTitle_Percent_Detail_(None, None, output)

        os.remove(script_file.name)

        if proc.returncode != 0:
            # error_output = '\n'.join(output_list)
            # Utils.sendReport('error', 'Could not run included workflow script: %s' % error_output)
            #self.errorMessage = 'Could not run included workflow script: %s' % error_output
            return

        return included_workflow

    def run(self, dry=False):
        if 'script' in self.item:
            included_workflow = self.includedWorkflowFromScript(self.item.get('script'))
        else:
            included_workflow = self.item['name']

        if included_workflow is None:
            Utils.sendReport('error', 'No included workflow was returned.')
            # self.errorMessage = 'No included workflow was returned.'
            return

        return included_workflow

    def __str__(self):
        return "Including workflow"


class StartOSInstallTask(ImagrTask):

    def run(self, dry=False):
        if self.reportDelegate:
            self.reportDelegate.sendReport('in_progress', 'starting macOS install: %s' % self.item.get('url'))

        ramdisk = self.item.get('ramdisk', False)

        if ramdisk:
            ramdisksource = Utils.RAMDisk(self.item, False, self.target,
                                          progress_callback=self.progressDelegate.updateProgressTitle_Percent_Detail_)
            if ramdisksource[0]:
                ositem = {
                    'ramdisk': True,
                    'type': 'startosinstall',
                    'url': ramdisksource[0]
                }
            else:
                if ramdisksource[1] is True:
                    ositem = self.item
                else:
                    self.target.EnsureMountedWithRefresh()
                    raise ImagrTaskError(ramdisksource[2])
        else:
            ositem = self.item

        if self.progressDelegate:
            self.progressDelegate.updateProgressTitle_Percent_Detail_(
                'Preparing macOS install...', -1, '')

        success, detail = osinstall.run(
            ositem, self.target.mountpoint,
            progress_method=self.progressDelegate.updateProgressTitle_Percent_Detail_)

        if not success:
            raise ImagrTaskError(detail)

        return None

    def __str__(self):
        return "Installing macOS from %s with RAMDisk: %r" % \
               (self.item.get('url', '(null)'), self.item.get('ramdisk', False))


class PartitionTask(ImagrTask):

    def _build_partition_command(self, partitions, partition_map, parent_disk):
        cmd = ['/usr/sbin/diskutil', 'partitionDisk', '/dev/' + parent_disk]
        partitionCmdList = list()
        future_target = False
        future_target_name = None

        def partition_switches(p):  # type: (dict) -> list
            return [
                # Default format type is "Journaled HFS+, case-insensitive"
                p.get('format_type', 'Journaled HFS+'),
                # Default name is "Macintosh HD"
                p.get('name', 'Macintosh HD'),
                # Default partition size is 100% of the disk size
                p.get('size', '100%'),
            ]

        if partitions:
            # A partition map was provided, so use that to repartition the disk
            for partition in partitions:
                target = partition_switches(partition)
                partitionCmdList.extend(target)
                if partition.get('target', False):
                    # logger.info("New target action found.")
                    # A new default target for future workflow actions was specified
                    future_target = True
                    future_target_name = partition.get('name', 'Macintosh HD')
            cmd.append('%d' % len(partitions))
            cmd.append(str(partition_map))
            cmd.extend(partitionCmdList)
        else:
            # No partition list was provided, so we just partition the target disk
            # with one volume, named 'Macintosh HD', using JHFS+, GPT Format
            cmd.extend(['1', 'GPTFormat', 'Journaled HFS+', 'Macintosh HD', '100%'])

        return cmd, future_target, future_target_name

    def run(self, dry=False):
        """
        Formats a target disk according to specifications.
        'partitions' is a list of dictionaries of partition mappings for names, sizes, formats.
        'partition_map' is a volume map type - MBR, GPT, or APM.

        Started partitioning on disk20
        Unmounting disk
        Creating the partition map
        Waiting for partitions to activate
        Formatting disk20s1 as Mac OS Extended (Journaled) with name First
        Mounting disk
        Formatting disk20s2 as Mac OS Extended (Journaled) with name Second
        Initialized /dev/rdisk20s2 as a 10 MB case-insensitive HFS Plus volume with a 512k journal
        Mounting disk
        Finished partitioning on disk20
        /dev/disk20 (disk image):
           #:                       TYPE NAME                    SIZE       IDENTIFIER
           0:      GUID_partition_scheme                        +21.0 MB    disk20
           1:                  Apple_HFS First                   10.5 MB    disk20s1
           2:                  Apple_HFS Second                  10.4 MB    disk20s2

        """
        partitions = self.item.get('partitions')
        partition_map = self.item.get('map')

        # self.target.mountpoint should be the actual volume we're targeting.
        # self.target is the macdisk object that can be queried for its parent disk
        parent_disk = self.target.Info()['ParentWholeDisk']
        # logger.info("Parent disk: %s" % parent_disk)

        cmd, future_target, future_target_name = self._build_partition_command(partitions, partition_map, parent_disk)
        # logger.debug(str(cmd))

        new_partitions = {}

        if not dry:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (stdoutdata, stderrdata) = proc.communicate()

            for line in stdoutdata.splitlines():
                match = re.search("Formatting (disk[0-9]+s[0-9]+) as (.*) with name (.*)", line)
                if match:
                    new_partitions[match.group(1)] = match.group(3)

            if stderrdata:
                #logger.error("Error occurred: %@", partErr)
                raise ImagrTaskError(stderrdata)
        # logger.debug(partOut)
        # At this point, we need to reload the possible targets, because '/Volumes/Macintosh HD' might not exist
        # self.should_update_volume_list = True
        if future_target:
            for new_disk_device, new_label in new_partitions.iteritems():
                print(new_disk_device, new_label)
                if new_label == future_target_name:
                    self._newTarget = macdisk.Disk(new_disk_device)
                    break

            # logger.info("New target volume mountpoint is %s" % self.targetVolume.mountpoint)

    def __str__(self):
        return "Partitioning Disk /dev/{} {} ({} partition(s))".format(
            self.target.Info()['ParentWholeDisk'],
            self.item.get('map'),
            len(self.item.get('partitions', [])),
        )


class EraseVolumeTask(ImagrTask):
    """Imagr Task: Erase a volume."""

    def run(self, dry=False):
        """
        Erases the target volume.
        'name' can be used to rename the volume on reformat.
        'format' can be used to specify a format type.
        If no options are provided, it will format the volume with name 'Macintosh HD' with JHFS+.
        """
        name = self.item.get('name', 'Macintosh HD')
        format = self.item.get('format', 'Journaled HFS+')

        cmd = ['/usr/sbin/diskutil', 'eraseVolume', format, name, self.target.mountpoint]
        # logger.debug(" ".join(cmd))

        if not dry:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (eraseOut, eraseErr) = proc.communicate()
            if eraseErr:
                NSLog("Error occured when erasing volume: %@", eraseErr)
                self.errorMessage = eraseErr
            NSLog("%@", eraseOut)

        # Reload possible targets, because '/Volumes/Macintosh HD' might not exist
        if name != 'Macintosh HD':
            # If the volume was renamed, or isn't named 'Macintosh HD', then we should recheck the volume list
            self.should_update_volume_list = True

    def __str__(self):
        return "Erasing volume at {} using label: {}".format(self.target.mountpoint, self.item.get('name'))


class FirstBootScriptTask(ImagrTask):
    """Imagr Task: Download and stage a script for run on first boot."""

    def run(self, dry=False):
        if self.reportDelegate:
            self.reportDelegate.sendReport('in_progress', 'Copying first boot script %s' % str(self.counter))

        if self.item.get('url'):
            if self.item.get('additional_headers'):
                (data, error) = Utils.downloadFile(self.item.get('url'), self.item.get('additional_headers'))
                self.copyFirstBootScript(data, self.counter)
            else:
                (data, error) = Utils.downloadFile(self.item.get('url'))
                self.copyFirstBootScript(data, self.counter)
        else:
            self.copyFirstBootScript(self.item.get('content'), self.counter)
        self.first_boot_items = True

    def copyFirstBootScript(self, script, counter):
        if not self.target.Mounted():
            self.target.Mount()

        try:
            self.copyScript(
                script, self.target.mountpoint, counter,
                progress_method=self.updateProgressTitle_Percent_Detail_)
        except:
            raise ImagrTaskError("Couldn't copy script %s" % str(counter))

    def copyScript(self, script, target, number, progress_method=None):
        """
        Copies a
         script to a specific volume
        """
        dest_dir = os.path.join(target, 'usr/local/first-boot/items')
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        dest_file = os.path.join(dest_dir, "%03d" % number)
        if progress_method:
            progress_method("Copying script to %s" % dest_file, 0, '')
        # convert placeholders
        if self.computerName or self.keyboard_layout_id or self.keyboard_layout_name or self.language or self.locale or self.timezone:
            script = Utils.replacePlaceholders(script, target, self.computerName, self.keyboard_layout_id, self.keyboard_layout_name, self.language, self.locale, self.timezone)
        else:
            script = Utils.replacePlaceholders(script, target)
        # write file
        with open(dest_file, "w") as text_file:
            text_file.write(script)
        # make executable
        os.chmod(dest_file, 0755)
        return dest_file


class FirstBootPackageTask(ImagrTask):
    """Imagr Task: Download and stage a .pkg for installation upon first boot."""

    def run(self, dry=False):
        self.updateProgressTitle_Percent_Detail_(
            'Copying packages for install on first boot...', -1, '')
        # mount the target
        if not self.target.Mounted():
            self.target.Mount()
        url = self.item.get('url')
        additional_headers = self.item.get('additional_headers')
        (output, error) = self.downloadPackage(url, self.target.mountpoint, counter,
                                               progress_method=self.updateProgressTitle_Percent_Detail_, additional_headers=additional_headers)
        if error:
            self.errorMessage = "Error copying first boot package %s - %s" % (url, error)
            return False

    def downloadPackage(self, url, target, number, progress_method=None, additional_headers=None):
        error = None
        dest_dir = os.path.join(target, 'usr/local/first-boot/items')
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        if not os.path.basename(url).endswith('.pkg') and not os.path.basename(url).endswith('.dmg'):
            error = "%s doesn't end with either '.pkg' or '.dmg'" % url
            return False, error
        if os.path.basename(url).endswith('.dmg'):
            NSLog("Copying pkg(s) from %@", url)
            (output, error) = self.copyPkgFromDmg(url, dest_dir, number)
        else:
            NSLog("Downloading pkg %@", url)
            package_name = "%03d-%s" % (number, os.path.basename(url))
            os.umask(0002)
            file = os.path.join(dest_dir, package_name)
            (output, error) = Utils.downloadChunks(url, file, progress_method=progress_method, additional_headers=additional_headers)

        return output, error

    def copyPkgFromDmg(self, url, dest_dir, number):
        error = None
        # We're going to mount the dmg
        try:
            dmgmountpoints = Utils.mountdmg(url)
            dmgmountpoint = dmgmountpoints[0]
        except:
            self.errorMessage = "Couldn't mount %s" % url
            return False, self.errorMessage

        # Now we're going to go over everything that ends .pkg or
        # .mpkg and install it
        pkg_list = []
        for package in os.listdir(dmgmountpoint):
            if package.endswith('.pkg') or package.endswith('.mpkg'):
                pkg = os.path.join(dmgmountpoint, package)
                dest_file = os.path.join(dest_dir, "%03d-%s" % (number, os.path.basename(pkg)))
                try:
                    if os.path.isfile(pkg):
                        shutil.copy(pkg, dest_file)
                    else:
                        shutil.copytree(pkg, dest_file)
                except:
                    error = "Couldn't copy %s" % pkg
                    return None, error
                pkg_list.append(dest_file)

        # Unmount it
        try:
            Utils.unmountdmg(dmgmountpoint)
        except:
            self.errorMessage = "Couldn't unmount %s" % dmgmountpoint
            return False, self.errorMessage

        return pkg_list, None


class ScriptTask(ImagrTask):
    """ImagrTask: Run a local or remote script inside the NetBoot/NetInstall environment."""

    def run(self, dry=False):
        if self.item.get('url'):
            data, error = Utils.downloadFile(self.item.get('url'), self.item.get('additional_headers', None))
            if error:
                raise ImagrTaskError(error)
        else:
            data = self.item.get('content')

        if self.progressDelegate:
            self.progressDelegate.updateProgressTitle_Percent_Detail_(
                'Preparing to run scripts...', -1, ''
            )

        # mount the target
        if not self.target.Mounted():
            self.target.Mount()

        retcode, error_output = self.runScript(
            data, self.target.mountpoint,
            progress_method=self.progressDelegate.updateProgressTitle_Percent_Detail_)

        if retcode != 0:
            if error_output is not None:
                self.errorMessage = error_output
            else:
                self.errorMessage = "Script %s returned a non-0 exit code" % str(int(counter))

    def runScript(self, script, target, progress_method=None):
        """
        Replaces placeholders in a script and then runs it.
        """
        # replace the placeholders in the script
        script = Utils.replacePlaceholders(script, target)
        error_output = None
        output_list = []
        # Copy script content to a temporary location and make executable
        script_file = tempfile.NamedTemporaryFile(delete=False)
        script_file.write(script)
        script_file.close()
        os.chmod(script_file.name, 0700)
        if progress_method:
            progress_method("Running script...", -1, '')
        proc = subprocess.Popen(script_file.name, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        while proc.poll() is None:
            output = proc.stdout.readline().strip().decode('UTF-8')
            output_list.append(output)
            if progress_method:
                progress_method(None, None, output)
        os.remove(script_file.name)
        if proc.returncode != 0:
            error_output = '\n'.join(output_list)
        return proc.returncode, error_output


class InstallPackageTask(ImagrTask):
    """Imagr Task: Download and install a .pkg from a remote URL."""

    def run(self, dry=False):
        url = self.item.get('url')
        additional_headers = self.item.get('additional_headers')

        if self.progressDelegate:
            self.progressDelegate.updateProgressTitle_Percent_Detail_('Installing packages...', -1, '')
        # mount the target
        self.target.EnsureMountedWithRefresh()

        package_name = os.path.basename(url)

        if package_name.endswith('.dmg'):
            # We're going to mount the dmg
            try:
                dmgmountpoints = Utils.mountdmg(url)
                dmgmountpoint = dmgmountpoints[0]
            except:
                self.errorMessage = "Couldn't mount %s" % url
                return False, self.errorMessage

            # Now we're going to go over everything that ends .pkg or
            # .mpkg and install it
            for package in os.listdir(dmgmountpoint):
                if package.endswith('.pkg') or package.endswith('.mpkg'):
                    pkg = os.path.join(dmgmountpoint, package)
                    retcode = self.installPkg(pkg, self.target, progress_method=self.progressDelegate.updateProgressTitle_Percent_Detail_)
                    if retcode != 0:
                        self.errorMessage = "Couldn't install %s" % pkg
                        return False

            # Unmount it
            try:
                Utils.unmountdmg(dmgmountpoint)
            except:
                self.errorMessage = "Couldn't unmount %s" % dmgmountpoint
                return False, self.errorMessage
        elif package_name.endswith('.pkg'):

            # Make our temp directory on the target
            temp_dir = tempfile.mkdtemp(dir=self.target.mountpoint)
            # Download it
            packagename = os.path.basename(url)
            (downloaded_file, error) = Utils.downloadChunks(url, os.path.join(temp_dir,
                                                                              packagename), additional_headers=additional_headers)
            if error:
                self.errorMessage = "Couldn't download - %s \n %s" % (url, error)
                return False
            # Install it
            retcode = self.installPkg(downloaded_file, self.target, progress_method=self.progressDelegate.updateProgressTitle_Percent_Detail_)
            if retcode != 0:
                self.errorMessage = "Couldn't install %s" % downloaded_file
                return False
            # Clean up after ourselves
            shutil.rmtree(temp_dir)
        else:
            raise ImagrTaskError("%s doesn't end with either '.pkg' or '.dmg'" % url)

    def installPkg(self, pkg, target, progress_method=None):
        """
        Installs a package on a specific volume
        """
        NSLog("Installing %@ to %@", pkg, target)
        if progress_method:
            progress_method("Installing %s" % os.path.basename(pkg), 0, '')
        cmd = ['/usr/sbin/installer', '-pkg', pkg, '-target', target, '-verboseR']
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while proc.poll() is None:
            output = proc.stdout.readline().strip().decode('UTF-8')
            if output.startswith("installer:"):
                msg = output[10:].rstrip("\n")
                if msg.startswith("PHASE:"):
                    phase = msg[6:]
                    if phase:
                        NSLog(phase)
                        if progress_method:
                            progress_method(None, None, phase)
                elif msg.startswith("STATUS:"):
                    status = msg[7:]
                    if status:
                        NSLog(status)
                        if progress_method:
                            progress_method(None, None, status)
                elif msg.startswith("%"):
                    percent = float(msg[1:])
                    NSLog("%@ percent complete", percent)
                    if progress_method:
                        progress_method(None, percent, None)
                elif msg.startswith(" Error"):
                    NSLog(msg)
                    if progress_method:
                        progress_method(None, None, msg)
                elif msg.startswith(" Cannot install"):
                    NSLog(msg)
                    if progress_method:
                        progress_method(None, None, msg)
                else:
                    NSLog(msg)
                    if progress_method:
                        progress_method(None, None, msg)

        return proc.returncode


class ImageTask(ImagrTask):
    """Imagr Task: Image task

    A wrapper around 'asr' to clone one disk object onto another.

    We run with `--puppetstrings` so that we get non-buffered output that we
    can actually read. Progress is delivered to the `progressDelegate` if it exists.

    Component workflow properties:

    :url: The source URL of the .dmg file to restore.
    :verify: (Default True) Verify the clone operation.
    :ramdisk: (Default False) Use a ramdisk to clone: downloads the source dmg into a ramdisk and restores from there.
        In some cases this may speed up restoration.
    """

    def run(self, dry=False):
        url = self.item.get('url')
        verify = self.item.get('verify', True)
        ramdisk = self.item.get('ramdisk', False)
        erase = self.item.get('erase', True)

        if self.reportDelegate:
            self.reportDelegate.sendReport('in_progress', 'Restoring DMG: %s' % url)

        target_ref = "/dev/%s" % self.target.deviceidentifier

        if ramdisk:
            ramdisk_size = Utils.getDMGSize(url)[0]

            # TODO: Normally 10% headroom is added for HFS overhead.
            ramdisk_dev, ramdisk_label = Utils.create_ramdisk(ramdisk_size)
            # TODO: Wait for volume to appear

            # Download DMG from url to ramdisk root
            if self.progressDelegate:
                self.progressDelegate.updateProgressTitle_Percent_Detail_("Downloading {}...".format(url), -1, "")

            ramdisk_volume = "/Volumes/{}".format(ramdisk_label)

            if self.progressDelegate:
                progress_callback = self.progressDelegate.updateProgressTitle_Percent_Detail_
            else:
                progress_callback = lambda t, p, d: None

            original_url = url
            url = Utils.downloadDMG(url, ramdisk_volume, progress_callback=progress_callback)

        source_is_apfs = Utils.is_apfs(url)
        if source_is_apfs:
            # logger.info("Source is APFS")
            # we need to restore to a whole disk here
            if not self.target.wholedisk:
                # logger.info("Source is not a whole disk")
                target_ref = "/dev/%s" % self.target._attributes['ParentWholeDisk']

        is_compatible, reason = Utils.is_source_target_compatible(url, self.target)
        if not is_compatible:
            self.target.EnsureMountedWithRefresh()
            raise ImagrTaskError(reason)

        command = ["/usr/sbin/asr", "restore", "--source", str(url),
                   "--target", target_ref, "--noprompt", "--puppetstrings"]
        # logger.debug(" ".join(command))
        self.target.Refresh()

        if 'FilesystemType' not in self.target._attributes:
            raise TypeError("FilesystemType not determined. You are probably trying to image an EFI System Partition")

        if erase:
            # check we can unmount the target... may as well fail here than later.
            if self.target.Mounted():
                self.target.Unmount()
            command.append("--erase")

        if not verify:
            command.append("--noverify")

        if self.progressDelegate:
            self.progressDelegate.updateProgressTitle_Percent_Detail_('Restoring %s' % url, -1, '')
        # logger.debug(str(command))
        task = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        while task.poll() is None:
            output = task.stdout.readline().strip()
            try:
                percent = int(output.split("\t")[1])
            except:
                percent = 0.001
            if len(output.split("\t")) == 4:
                if output.split("\t")[3] == "restore":
                    message = "Restoring: "+ str(percent) + "%"
                elif output.split("\t")[3] == "verify":
                    message = "Verifying: "+ str(percent) + "%"
                else:
                    message = ""
            else:
                message = ""
            if percent == 0:
                percent = 0.001

            if self.progressDelegate:
                self.progressDelegate.updateProgressTitle_Percent_Detail_(None, percent, message)

        (unused_stdout, stderr) = task.communicate()
        if task.returncode:
            self.target.EnsureMountedWithRefresh()
            raise ImagrTaskError("Cloning Error: %s" % stderr)
        if task.poll() == 0:
            self.target.EnsureMountedWithRefresh()
            if 'ramdisk' in url:
                # logger.info(u"Detaching RAM Disk post imaging.")
                detachcommand = ["/usr/bin/hdiutil", "detach",
                                 ramdisk_dev]
                subprocess.check_call(detachcommand)
            return True

class ReformatTask(ImagrTask):
    """Imagr Task: Reformat
        
    Reformats the target volume.
    The format and name are retained, so no arguments are required.
    """
    
    def run(self, dry=False):
        cmd = ['/usr/sbin/diskutil', 'reformat', self.target.mountpoint]
        NSLog("%@", cmd)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (eraseOut, eraseErr) = proc.communicate()
        if eraseErr:
            NSLog("Error occured when reformatting volume: %@", eraseErr)
            self.errorMessage = eraseErr
        NSLog("%@", eraseOut)
        return True
