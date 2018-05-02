# -*- coding: utf-8 -*-
#
#  MainController.py
#  Imagr
#
#  Created by Graham Gilbert on 04/04/2015.
#  Copyright (c) 2015 Graham Gilbert. All rights reserved.
#

import objc
import FoundationPlist
import os
from SystemConfiguration import *
from Foundation import *
from AppKit import *
from Cocoa import *
from Quartz.CoreGraphics import *

import subprocess
import Utils
import PyObjCTools
import Quartz
from tasks import ImagrTask


class MainController(NSObject):

    mainWindow = objc.IBOutlet()
    backgroundWindow = objc.IBOutlet()

    utilities_menu = objc.IBOutlet()
    help_menu = objc.IBOutlet()

    theTabView = objc.IBOutlet()
    introTab = objc.IBOutlet()
    loginTab = objc.IBOutlet()
    mainTab = objc.IBOutlet()
    errorTab = objc.IBOutlet()
    computerNameTab = objc.IBOutlet()

    password = objc.IBOutlet()
    passwordLabel = objc.IBOutlet()
    loginLabel = objc.IBOutlet()
    loginButton = objc.IBOutlet()
    errorField = objc.IBOutlet()

    progressIndicator = objc.IBOutlet()
    progressText = objc.IBOutlet()

    authenticationPanel = objc.IBOutlet()
    authenticationPanelUsernameField = objc.IBOutlet()
    authenticationPanelPasswordField = objc.IBOutlet()

    startUpDiskPanel = objc.IBOutlet()
    startUpDiskText = objc.IBOutlet()
    startupDiskCancelButton = objc.IBOutlet()
    startupDiskDropdown = objc.IBOutlet()
    startupDiskRestartButton = objc.IBOutlet()

    chooseTargetPanel = objc.IBOutlet()
    chooseTargetDropDown = objc.IBOutlet()
    chooseTargetCancelButton = objc.IBOutlet()
    chooseTargetPanelSelectTarget = objc.IBOutlet()

    cancelAndRestartButton = objc.IBOutlet()
    reloadWorkflowsButton = objc.IBOutlet()
    reloadWorkflowsMenuItem = objc.IBOutlet()
    chooseWorkflowDropDown = objc.IBOutlet()
    chooseWorkflowLabel = objc.IBOutlet()

    runWorkflowButton = objc.IBOutlet()
    workflowDescriptionView = objc.IBOutlet()
    workflowDescription = objc.IBOutlet()

    imagingProgress = objc.IBOutlet()
    imagingLabel = objc.IBOutlet()
    imagingProgressPanel = objc.IBOutlet()
    imagingProgressDetail = objc.IBOutlet()

    computerNameInput = objc.IBOutlet()
    computerNameButton = objc.IBOutlet()

    countdownWarningImage = objc.IBOutlet()
    countdownCancelButton = objc.IBOutlet()

    # former globals, now instance variables
    hasLoggedIn = None
    volumes = None
    passwordHash = None
    workflows = None
    targetVolume = None
    #workVolume = None
    selectedWorkflow = None
    defaultWorkflow = None
    parentWorkflow = None
    packages_to_install = None
    restartAction = None
    blessTarget = None
    errorMessage = None
    alert = None
    workflow_is_running = False
    computerName = None
    counter = 0.0
    first_boot_items = None
    waitForNetwork = True
    firstBootReboot = True
    autoRunTime = 30
    autorunWorkflow = None
    cancelledAutorun = False
    authenticatedUsername = None
    authenticatedPassword = None

    def errorPanel(self, error):
        if error:
            errorText = str(error)
        else:
            errorText = "Unknown error"

        # Send a report to the URL if it's configured
        Utils.sendReport('error', errorText)

        self.alert = NSAlert.alertWithMessageText_defaultButton_alternateButton_otherButton_informativeTextWithFormat_(
            NSLocalizedString(errorText, None),
            NSLocalizedString(u"Choose Startup Disk", None),
            NSLocalizedString(u"Reload Workflows", None),
            objc.nil,
            NSLocalizedString(u"", None))

        self.errorMessage = None
        self.alert.beginSheetModalForWindow_modalDelegate_didEndSelector_contextInfo_(
            self.mainWindow, self, self.errorPanelDidEnd_returnCode_contextInfo_, objc.nil)

    @PyObjCTools.AppHelper.endSheetMethod
    def errorPanelDidEnd_returnCode_contextInfo_(self, alert, returncode, contextinfo):
        # 0 = reload workflows
        # 1 = Restart
        if returncode == 0:
            self.errorMessage = None
            self.reloadWorkflows_(self)
        else:
            self.setStartupDisk_(self)

    def runStartupTasks(self):
        NSLog(u"background_window is set to %@", repr(self.backgroundWindowSetting()))

        if self.backgroundWindowSetting() == u"always":
            self.showBackgroundWindow()

        self.mainWindow.center()
        self.mainWindow.setCanBecomeVisibleWithoutLogin_(True)
        # Run app startup - get the images, password, volumes - anything that takes a while
        self.progressText.setStringValue_("Application Starting...")
        self.chooseWorkflowDropDown.removeAllItems()
        self.progressIndicator.setIndeterminate_(True)
        self.progressIndicator.setUsesThreadedAnimation_(True)
        self.progressIndicator.startAnimation_(self)
        self.registerForWorkspaceNotifications()
        NSThread.detachNewThreadSelector_toTarget_withObject_(self.loadData, self, None)

    def backgroundWindowSetting(self):
        return Utils.get_preference(u"background_window") or u"auto"

    def showBackgroundWindow(self):
        # Create a background window that covers the whole screen.
        NSLog(u"Showing background window")
        rect = NSScreen.mainScreen().frame()
        self.backgroundWindow.setCanBecomeVisibleWithoutLogin_(True)
        self.backgroundWindow.setFrame_display_(rect, True)
        backgroundColor = NSColor.darkGrayColor()
        self.backgroundWindow.setBackgroundColor_(backgroundColor)
        self.backgroundWindow.setOpaque_(False)
        self.backgroundWindow.setIgnoresMouseEvents_(False)
        self.backgroundWindow.setAlphaValue_(1.0)
        self.backgroundWindow.orderFrontRegardless()
        self.backgroundWindow.setLevel_(kCGNormalWindowLevel - 1)
        self.backgroundWindow.setCollectionBehavior_(NSWindowCollectionBehaviorStationary | NSWindowCollectionBehaviorCanJoinAllSpaces)

    def loadBackgroundImage(self, urlString):
        if self.backgroundWindowSetting() == u"never":
            return
        NSLog(u"Loading background image")
        if self.backgroundWindowSetting() == u"auto":
            runningApps = [x.bundleIdentifier() for x in NSWorkspace.sharedWorkspace().runningApplications()]
            if u"com.apple.dock" not in runningApps:
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    self.showBackgroundWindow, None, YES)
            else:
                NSLog(u"Not showing background window as Dock.app is running")
                return

        def gcd(a, b):
            """Return greatest common divisor of two numbers"""
            if b == 0:
                return a
            return gcd(b, a % b)

        if not urlString.endswith(u"?"):
            try:
                verplist = FoundationPlist.readPlist("/System/Library/CoreServices/SystemVersion.plist")
                osver = verplist[u"ProductUserVisibleVersion"]
                osbuild = verplist[u"ProductBuildVersion"]
                size = NSScreen.mainScreen().frame().size
                w = int(size.width)
                h = int(size.height)
                divisor = gcd(w, h)
                aw = w / divisor
                ah = h / divisor
                urlString += u"?osver=%s&osbuild=%s&w=%d&h=%d&a=%d-%d" % (osver, osbuild, w, h, aw, ah)
            except:
                pass
        url = NSURL.URLWithString_(urlString)
        image = NSImage.alloc().initWithContentsOfURL_(url)
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            self.setBackgroundImage, image, YES)

    def setBackgroundImage(self, image):
        self.backgroundWindow.contentView().setWantsLayer_(True)
        self.backgroundWindow.contentView().layer().setContents_(image)

    def registerForWorkspaceNotifications(self):
        nc = NSWorkspace.sharedWorkspace().notificationCenter()
        nc.addObserver_selector_name_object_(
            self, self.didReceiveWorkspaceNotification, NSWorkspaceDidMountNotification, None)
        nc.addObserver_selector_name_object_(
            self, self.didReceiveWorkspaceNotification, NSWorkspaceDidUnmountNotification, None)
        nc.addObserver_selector_name_object_(
            self, self.didReceiveWorkspaceNotification, NSWorkspaceDidRenameVolumeNotification, None)

    def didReceiveWorkspaceNotification(self, notification):
        if self.workflow_is_running:
            self.should_update_volume_list = True
            return
        notification_name = notification.name()
        user_info = notification.userInfo()
        NSLog("NSWorkspace notification was: %@", notification_name)
        if notification_name == NSWorkspaceDidMountNotification:
            new_volume = user_info['NSDevicePath']
            NSLog("%@ was mounted", new_volume)
        elif notification_name == NSWorkspaceDidUnmountNotification:
            removed_volume = user_info['NSDevicePath']
            NSLog("%@ was unmounted", removed_volume)
        elif notification_name == NSWorkspaceDidRenameVolumeNotification:
            pass
        self.reloadVolumes()

    def validTargetVolumes(self):
        volume_list = []
        for volume in self.volumes:
            if volume.mountpoint == '/':
                continue
            
            if not volume.mountpoint.startswith("/Volumes/"):
                continue
            
            if not volume.writable:
                continue

            volume_list.append(volume.mountpoint)
        return volume_list

    def reloadVolumes(self):
        self.volumes = Utils.mountedVolumes()
        self.chooseTargetDropDown.removeAllItems()
        volume_list = self.validTargetVolumes()
        self.chooseTargetDropDown.addItemsWithTitles_(volume_list)
        # reselect previously selected target if possible
        if self.targetVolume:
            self.chooseTargetDropDown.selectItemWithTitle_(self.targetVolume.mountpoint)
            selected_volume = self.chooseTargetDropDown.titleOfSelectedItem()
        else:
            selected_volume = volume_list[0]
            self.chooseTargetDropDown.selectItemWithTitle_(selected_volume)
        for volume in self.volumes:
            if str(volume.mountpoint) == str(selected_volume):
                self.targetVolume = volume

    def expandImagingProgressPanel(self):
        self.imagingProgressPanel.setContentSize_(NSSize(466, 119))
        self.countdownWarningImage.setHidden_(False)
        self.countdownCancelButton.setHidden_(False)
        self.imagingLabel.setFrameOrigin_(NSPoint(89, 87))
        self.imagingLabel.setFrameSize_(NSSize(359, 17))
        self.imagingProgress.setFrameOrigin_(NSPoint(91, 60))
        self.imagingProgress.setFrameSize_(NSSize(355, 20))
        self.imagingProgressDetail.setFrameOrigin_(NSPoint(89, 41))
        self.imagingProgressDetail.setFrameSize_(NSSize(360, 17))

    def contractImagingProgressPanel(self):
        self.imagingProgressPanel.setContentSize_(NSSize(466, 98))
        self.countdownWarningImage.setHidden_(True)
        self.countdownCancelButton.setHidden_(True)
        self.imagingLabel.setFrameOrigin_(NSPoint(17, 66))
        self.imagingLabel.setFrameSize_(NSSize(431, 17))
        self.imagingProgress.setFrameOrigin_(NSPoint(20, 39))
        self.imagingProgress.setFrameSize_(NSSize(426, 20))
        self.imagingProgressDetail.setFrameOrigin_(NSPoint(18, 20))
        self.imagingProgressDetail.setFrameSize_(NSSize(431, 17))

    def showAuthenticationPanel(self):
        """Show the authentication panel"""
        NSApp.beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            self.authenticationPanel, self.mainWindow, self, None, None)

    @objc.IBAction
    def cancelAuthenticationPanel_(self, sender):
        """Called when user clicks 'Quit' in the authentication panel"""
        NSApp.endSheet_(self.authenticationPanel)
        NSApp.terminate_(self)

    @objc.IBAction
    def endAuthenticationPanel_(self, sender):
        """Called when user clicks 'Continue' in the authentication panel"""
        # store the username and password
        self.authenticatedUsername = self.authenticationPanelUsernameField.stringValue()
        self.authenticatedPassword = self.authenticationPanelPasswordField.stringValue()
        NSApp.endSheet_(self.authenticationPanel)
        self.authenticationPanel.orderOut_(self)
        # re-request the workflows.plist, this time with username and password available
        NSThread.detachNewThreadSelector_toTarget_withObject_(self.loadData, self, None)

    def loadData(self):
        pool = NSAutoreleasePool.alloc().init()
        self.buildUtilitiesMenu()
        self.volumes = Utils.mountedVolumes()
        theURL = Utils.getServerURL()

        if theURL:
            plistData = None
            tries = 0
            while (not plistData) and (tries < 3):
                tries += 1
                (plistData, error) = Utils.downloadFile(
                    theURL, username=self.authenticatedUsername, password=self.authenticatedPassword)
                if error:
                    try:
                        if error.reason[0] in [401, -1012, -1013]:
                            # 401:   HTTP status code: authentication required
                            # -1012: NSURLErrorDomain code "User cancelled authentication" -- returned
                            #        when we try a given name and password and fail
                            # -1013: NSURLErrorDomain code "User Authentication Required"
                            NSLog("Configuration plist requires authentication.")
                            # show authentication panel using the main thread
                            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                                self.showAuthenticationPanel, None, YES)
                            del pool
                            return
                        elif error.reason[0] < 0:
                            NSLog("Failed to load configuration plist: %@", repr(error.reason))
                            # Possibly ssl error due to a bad clock, try setting the time.
                            Utils.setDate()
                    except AttributeError, IndexError:
                        pass

            if plistData:
                try:
                    converted_plist = FoundationPlist.readPlistFromString(plistData)
                except:
                    self.errorMessage = "Configuration plist couldn't be read."
                    converted_plist = {}

                self.waitForNetwork = converted_plist.get('wait_for_network', True)
                self.autoRunTime = converted_plist.get('autorun_time', 30)

                urlString = converted_plist.get('background_image', None)
                if urlString is not None:
                    NSThread.detachNewThreadSelector_toTarget_withObject_(self.loadBackgroundImage, self, urlString)

                self.passwordHash = converted_plist.get('password', None)
                if self.passwordHash is None:
                    self.hasLoggedIn = True  # Bypass the login form if no password is given.

                self.workflows = converted_plist.get('workflows', None)
                if self.workflows is None:
                    self.errorMessage = "No workflows found in the configuration plist."

                self.defaultWorkflow = converted_plist.get('default_workflow', None)
                self.autorunWorkflow = converted_plist.get('autorun', None)
                # If we've already cancelled autorun, don't bother trying to autorun again.
                if self.cancelledAutorun:
                    self.autorunWorkflow = None
            else:
                self.errorMessage = "Couldn't get configuration plist. \n %s. \n '%s'" % (error.reason, error.url)
        else:
            self.errorMessage = "Configuration URL wasn't set."
        Utils.setup_logging()
        Utils.sendReport('in_progress', 'Imagr is starting up...')
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            self.loadDataComplete, None, YES)
        del pool

    def loadDataComplete(self):
        #self.reloadWorkflowsMenuItem.setEnabled_(True)
        if self.errorMessage:
            self.theTabView.selectTabViewItem_(self.errorTab)
            self.errorPanel(self.errorMessage)
        else:
            if self.hasLoggedIn:
                self.enableWorkflowViewControls()
                self.theTabView.selectTabViewItem_(self.mainTab)
                self.chooseImagingTarget_(None)

                self.isAutorun()
            else:
                self.theTabView.selectTabViewItem_(self.loginTab)
                self.mainWindow.makeFirstResponder_(self.password)

    def isAutorun(self):
        if self.autorunWorkflow:
            self.countdownOnThreadPrep()

    @objc.IBAction
    def reloadWorkflows_(self, sender):
        self.reloadWorkflowsMenuItem.setEnabled_(False)
        self.progressText.setStringValue_("Reloading workflows...")
        self.progressIndicator.setIndeterminate_(True)
        self.progressIndicator.setUsesThreadedAnimation_(True)
        self.progressIndicator.startAnimation_(self)
        self.theTabView.selectTabViewItem_(self.introTab)
        NSThread.detachNewThreadSelector_toTarget_withObject_(self.loadData, self, None)

    @objc.IBAction
    def login_(self, sender):
        if self.passwordHash:
            password_value = self.password.stringValue()
            if Utils.getPasswordHash(password_value) != self.passwordHash or password_value == "":
                self.errorField.setEnabled_(sender)
                self.errorField.setStringValue_("Incorrect password")
                self.shakeWindow()

            else:
                self.theTabView.selectTabViewItem_(self.mainTab)
                self.chooseImagingTarget_(None)
                self.enableAllButtons_(self)
                self.hasLoggedIn = True

                self.isAutorun()

    @objc.IBAction
    def setStartupDisk_(self, sender):
        if self.alert:
            self.alert.window().orderOut_(self)
            self.alert = None

        # Prefer to use the built in Startup disk pane
        if os.path.exists("/Applications/Utilities/Startup Disk.app"):
            Utils.launchApp("/Applications/Utilities/Startup Disk.app")
        else:
            self.restartAction = 'restart'
            # This stops the console being spammed with: unlockFocus called too many times. Called on <NSButton
            NSGraphicsContext.saveGraphicsState()
            self.disableAllButtons_(sender)
            # clear out the default junk in the dropdown
            self.startupDiskDropdown.removeAllItems()
            volume_list = []
            for volume in self.volumes:
                volume_list.append(volume.mountpoint)

            # Let's add the items to the popup
            self.startupDiskDropdown.addItemsWithTitles_(volume_list)
            NSApp.beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
                self.startUpDiskPanel, self.mainWindow, self, None, None)
            NSGraphicsContext.restoreGraphicsState()


    @objc.IBAction
    def closeStartUpDisk_(self, sender):
        self.enableAllButtons_(sender)
        NSApp.endSheet_(self.startUpDiskPanel)
        self.startUpDiskPanel.orderOut_(self)

    @objc.IBAction
    def openProgress_(self, sender):
        NSApp.beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            self.progressPanel, self.mainWindow, self, None, None)

    @objc.IBAction
    def chooseImagingTarget_(self, sender):
        self.chooseTargetDropDown.removeAllItems()
        volume_list = self.validTargetVolumes()
         # No writable volumes, this is bad.
        if len(volume_list) == 0:
            alert = NSAlert.alertWithMessageText_defaultButton_alternateButton_otherButton_informativeTextWithFormat_(
                NSLocalizedString(u"No writable volumes found", None),
                NSLocalizedString(u"Restart", None),
                NSLocalizedString(u"Open Disk Utility", None),
                objc.nil,
                NSLocalizedString(u"No writable volumes were found on this Mac.", None))
            alert.beginSheetModalForWindow_modalDelegate_didEndSelector_contextInfo_(
                self.mainWindow, self, self.noVolAlertDidEnd_returnCode_contextInfo_, objc.nil)
        else:
            self.chooseTargetDropDown.addItemsWithTitles_(volume_list)
            if self.targetVolume:
                self.chooseTargetDropDown.selectItemWithTitle_(self.targetVolume.mountpoint)

            selected_volume = self.chooseTargetDropDown.titleOfSelectedItem()
            for volume in self.volumes:
                if str(volume.mountpoint) == str(selected_volume):
                    #imaging_target = volume
                    self.targetVolume = volume
                    break
            self.selectWorkflow_(sender)

    @PyObjCTools.AppHelper.endSheetMethod
    def noVolAlertDidEnd_returnCode_contextInfo_(self, alert, returncode, contextinfo):
        if returncode == NSAlertDefaultReturn:
            self.setStartupDisk_(None)
        else:
            Utils.launchApp('/Applications/Utilities/Disk Utility.app')
            alert = NSAlert.alertWithMessageText_defaultButton_alternateButton_otherButton_informativeTextWithFormat_(
                NSLocalizedString(u"Rescan for volumes", None),
                NSLocalizedString(u"Rescan", None),
                objc.nil,
                objc.nil,
                NSLocalizedString(u"Rescan for volumes.", None))

            alert.beginSheetModalForWindow_modalDelegate_didEndSelector_contextInfo_(
                self.mainWindow, self, self.rescanAlertDidEnd_returnCode_contextInfo_, objc.nil)

    @PyObjCTools.AppHelper.endSheetMethod
    def rescanAlertDidEnd_returnCode_contextInfo_(self, alert, returncode, contextinfo):
        # NSWorkspaceNotifications should take care of updating our list of available volumes
        # Need to reload workflows
        self.reloadWorkflows_(self)

    @objc.IBAction
    def selectImagingTarget_(self, sender):
        volume_name = self.chooseTargetDropDown.titleOfSelectedItem()
        for volume in self.volumes:
            if str(volume.mountpoint) == str(volume_name):
                self.targetVolume = volume
                break
        NSLog("Imaging target is %@", self.targetVolume.mountpoint)


    @objc.IBAction
    def closeImagingTarget_(self, sender):
        self.enableAllButtons_(sender)
        NSApp.endSheet_(self.chooseTargetPanel)
        self.chooseTargetPanel.orderOut_(self)
        self.setStartupDisk_(sender)

    @objc.IBAction
    def selectWorkflow_(self, sender):
        self.chooseWorkflowDropDown.removeAllItems()
        workflow_list = []
        for workflow in self.workflows:
            if 'hidden' in workflow:
                # Don't add 'hidden' workflows to the list
                if workflow['hidden'] == False:
                    workflow_list.append(workflow['name'])
            else:
                # If not specified, assume visible
                workflow_list.append(workflow['name'])

        self.chooseWorkflowDropDown.addItemsWithTitles_(workflow_list)

        # The current selection is deselected if a nil or non-existent title is given
        if self.defaultWorkflow:
            self.chooseWorkflowDropDown.selectItemWithTitle_(self.defaultWorkflow)

        self.chooseWorkflowDropDownDidChange_(sender)

    @objc.IBAction
    def chooseWorkflowDropDownDidChange_(self, sender):
        selected_workflow = self.chooseWorkflowDropDown.titleOfSelectedItem()
        for workflow in self.workflows:
            if selected_workflow == workflow['name']:
                try:
                    self.workflowDescription.setString_(workflow['description'])
                except:
                    self.workflowDescription.setString_("")
                break

    def enableWorkflowDescriptionView_(self, enabled):
        # See https://developer.apple.com/library/mac/qa/qa1461/_index.html
        self.workflowDescription.setSelectable_(enabled)
        if enabled:
            self.workflowDescription.setTextColor_(NSColor.controlTextColor())
        else:
            self.workflowDescription.setTextColor_(NSColor.disabledControlTextColor())

    def disableWorkflowViewControls(self):
        self.setWorkflowViewControlsEnabled(enabled=False)

    def enableWorkflowViewControls(self):
        self.setWorkflowViewControlsEnabled()
    
    def setWorkflowViewControlsEnabled(self, enabled=True):
        self.reloadWorkflowsButton.setEnabled_(enabled)
        self.reloadWorkflowsMenuItem.setEnabled_(enabled)
        self.cancelAndRestartButton.setEnabled_(enabled)
        self.chooseWorkflowLabel.setEnabled_(enabled)
        self.chooseTargetDropDown.setEnabled_(enabled)
        self.chooseWorkflowDropDown.setEnabled_(enabled)
        self.enableWorkflowDescriptionView_(enabled)
        self.runWorkflowButton.setEnabled_(enabled)
        self.cancelAndRestartButton.setEnabled_(enabled)

    @objc.IBAction
    def runWorkflow_(self, sender):
        """Set up the selected workflow to run on secondary thread"""
        self.workflow_is_running = True
        selected_workflow = self.chooseWorkflowDropDown.titleOfSelectedItem()

        if self.autorunWorkflow:
            selected_workflow = self.autorunWorkflow

        # let's get the workflow
        self.selectedWorkflow = None
        for workflow in self.workflows:
            if selected_workflow == workflow['name']:
                self.selectedWorkflow = workflow
                break
        if self.selectedWorkflow:
            if 'restart_action' in self.selectedWorkflow:
                self.restartAction = self.selectedWorkflow['restart_action']
            if 'first_boot_reboot' in self.selectedWorkflow:
                self.firstBootReboot = self.selectedWorkflow['first_boot_reboot']
            if 'bless_target' in self.selectedWorkflow:
                self.blessTarget = self.selectedWorkflow['bless_target']
            else:
                self.blessTarget = True

            # Show the computer name tab if needed. I hate waiting to put in the
            # name in DS.
            settingName = False
            for item in self.selectedWorkflow['components']:
                if self.checkForNameComponent(item):
                    self.getComputerName_(item)
                    settingName = True
                    break

            if not settingName:
                self.workflowOnThreadPrep()

    def checkForNameComponent(self, item):
        if item.get('type') == 'computer_name':
            return True
        if item.get('type') == 'included_workflow':
            included_workflow = self.getIncludedWorkflow(item)
            for workflow in self.workflows:
                if workflow['name'] == included_workflow:
                    for new_item in workflow['components']:
                        if self.checkForNameComponent(new_item):
                            return True

        return False

    def workflowOnThreadPrep(self):
        self.disableWorkflowViewControls()
        Utils.sendReport('in_progress', 'Preparing to run workflow %s...' % self.selectedWorkflow['name'])
        self.imagingLabel.setStringValue_("Preparing to run workflow...")
        self.imagingProgressDetail.setStringValue_('')
        self.contractImagingProgressPanel()
        NSApp.beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            self.imagingProgressPanel, self.mainWindow, self, None, None)
        # initialize the progress bar
        self.imagingProgress.setMinValue_(0.0)
        self.imagingProgress.setMaxValue_(100.0)
        self.imagingProgress.setIndeterminate_(True)
        self.imagingProgress.setUsesThreadedAnimation_(True)
        self.imagingProgress.startAnimation_(self)
        NSThread.detachNewThreadSelector_toTarget_withObject_(
            self.processWorkflowOnThread, self, None)

    def countdownOnThreadPrep(self):
        self.disableWorkflowViewControls()
        self.imagingLabel.setStringValue_("Preparing to run {} on {}".format(self.autorunWorkflow, self.targetVolume.mountpoint))
        #self.imagingProgressDetail.setStringValue_('')
        self.expandImagingProgressPanel()
        NSApp.beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            self.imagingProgressPanel, self.mainWindow, self, None, None)
        # initialize the progress bar
        self.imagingProgress.setMinValue_(0.0)
        self.imagingProgress.setMaxValue_(30.0)
        self.imagingProgress.setIndeterminate_(True)
        self.imagingProgress.setUsesThreadedAnimation_(True)
        self.imagingProgress.startAnimation_(self)
        NSThread.detachNewThreadSelector_toTarget_withObject_(
            self.processCountdownOnThread, self, None)

    def processCountdownOnThread(self, sender):
        """Count down for 30s or admin provided"""
        countdown = self.autoRunTime
        #pool = NSAutoreleasePool.alloc().init()
        if self.autorunWorkflow and self.targetVolume:
            self.should_update_volume_list = False

            # Count down for 30s or admin provided.
            for remaining in range(countdown, 0, -1):
                if not self.autorunWorkflow:
                    break

                self.updateProgressTitle_Percent_Detail_(None, countdown - remaining, "Beginning in {}s".format(remaining))
                import time
                time.sleep(1)

        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            self.processCountdownOnThreadComplete, None, YES)
        #del pool

    def processCountdownOnThreadComplete(self):
        """Done running countdown, start the default workflow"""
        NSApp.endSheet_(self.imagingProgressPanel)
        self.imagingProgressPanel.orderOut_(self)

        # Make sure the user still wants to autorun the default workflow (i.e. hasn't clicked cancel).
        if self.autorunWorkflow:
            self.runWorkflow_(None)

    @objc.IBAction
    def cancelCountdown_(self, sender):
        """The user didn't want to automatically run the default workflow after all."""
        self.autorunWorkflow = None
        # Avoid trying to autorun again.
        self.cancelledAutorun = True
        self.enableWorkflowViewControls()

    def updateProgressWithInfo_(self, info):
        '''UI stuff should be done on the main thread. Yet we do all our interesting work
        on a secondary thread. So to update the UI, the secondary thread should call this
        method using performSelectorOnMainThread_withObject_waitUntilDone_'''
        if 'title' in info.keys():
            self.imagingLabel.setStringValue_(info['title'])
        if 'percent' in info.keys():
            if float(info['percent']) < 0:
                if not self.imagingProgress.isIndeterminate():
                    self.imagingProgress.setIndeterminate_(True)
                    self.imagingProgress.startAnimation_(self)
            else:
                if self.imagingProgress.isIndeterminate():
                    self.imagingProgress.stopAnimation_(self)
                    self.imagingProgress.setIndeterminate_(False)
                self.imagingProgress.setDoubleValue_(float(info['percent']))
        if 'detail' in info.keys():
            self.imagingProgressDetail.setStringValue_(info['detail'])

    def updateProgressTitle_Percent_Detail_(self, title, percent, detail):
        '''Wrapper method that calls the UI update method on the main thread'''
        info = {}
        if title is not None:
            info['title'] = title
        if percent is not None:
            info['percent'] = percent
        if detail is not None:
            info['detail'] = detail
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            self.updateProgressWithInfo_, info, objc.NO)

    def setupFirstBootTools(self):
        # copy bits for first boot script
        packages_dir = os.path.join(
            self.targetVolume.mountpoint, 'usr/local/first-boot/')
        if not os.path.exists(packages_dir):
            os.makedirs(packages_dir)
        Utils.copyFirstBoot(self.targetVolume.mountpoint,
                            self.waitForNetwork, self.firstBootReboot)

    def processWorkflowOnThread(self, sender):
        '''Process the selected workflow'''
        pool = NSAutoreleasePool.alloc().init()
        if self.selectedWorkflow:
            # count all of the workflow items - are we still using this?
            components = [item for item in self.selectedWorkflow['components']]
            component_count = len(components)

            self.should_update_volume_list = False

            for item in self.selectedWorkflow['components']:
                if (item.get('type') == 'startosinstall' and
                        self.first_boot_items):
                    # we won't get a chance to do this after this component
                    self.setupFirstBootTools()
                self.runComponent(item)
            if self.first_boot_items:
                self.setupFirstBootTools()

        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            self.processWorkflowOnThreadComplete, None, YES)
        del pool

    def processWorkflowOnThreadComplete(self):
        '''Done running workflow, restart to imaged volume'''
        NSApp.endSheet_(self.imagingProgressPanel)
        self.imagingProgressPanel.orderOut_(self)
        self.workflow_is_running = False

        # Disable autorun so users are able to select additional workflows to run.
        self.autorunWorkflow = None

        Utils.sendReport('success', 'Finished running %s.' % self.selectedWorkflow['name'])

        # Bless the target if we need to
        if self.blessTarget == True:
            try:
                self.targetVolume.SetStartupDisk()
            except:
                for volume in self.volumes:
                    if str(volume.mountpoint) == str(self.targetVolume.mountpoint):
                        volume.SetStartupDisk()
        if self.errorMessage:
            self.theTabView.selectTabViewItem_(self.errorTab)
            self.errorPanel(self.errorMessage)
        elif self.restartAction == 'restart' or self.restartAction == 'shutdown':
            self.restartToImagedVolume()
        else:
            if self.should_update_volume_list == True:
                NSLog("Refreshing volume list.")
                self.reloadVolumes()
            self.openEndWorkflowPanel()

    def runComponent(self, item):
        """Run the selected workflow component"""
        # No point carrying on if something is broken
        if not self.errorMessage:
            self.counter = self.counter + 1.0

            task = ImagrTask.taskForItem_target_(item, self.targetVolume)
            task.progressDelegate = self
            Utils.sendReport('in_progress', 'Running task: %s' % task)
            include_workflow = task.run()

            if isinstance(include_workflow, str):
                for workflow in self.workflows:
                    if include_workflow.strip() == workflow['name'].strip():
                        # logger.info("Included workflow: %s" % str(included_workflow))
                        # run the workflow
                        for component in workflow['components']:
                            self.runComponent(component)
                        return
            elif isinstance(include_workflow, list):
                for component in include_workflow:
                    self.runComponent(component)
            else:
                pass  # Nothing given


    def runIncludedWorkflow(self, item):
        '''Runs an included workflow'''

        included_workflow = self.getIncludedWorkflow(item)
        if included_workflow:
            for workflow in self.workflows:
                if included_workflow.strip() == workflow['name'].strip():
                    NSLog(u"Included Workflow: %@", str(included_workflow))
                    # run the workflow
                    for component in workflow['components']:
                        self.runComponent(component)
                    return
            else:
                Utils.sendReport('error', 'Could not find included workflow %s' % included_workflow)
                self.errorMessage = 'Could not find included workflow %s' % included_workflow
        else:
            Utils.sendReport('error', 'No included workflow passed %s' % included_workflow)
            self.errorMessage = 'No included workflow passed %s' % included_workflow

    def getComputerName_(self, component):
        auto_run = component.get('auto', False)
        hardware_info = Utils.get_hardware_info()

        # Try to get existing HostName
        try:
            preferencePath = os.path.join(self.targetVolume.mountpoint,'Library/Preferences/SystemConfiguration/preferences.plist')
            preferencePlist = FoundationPlist.readPlist(preferencePath)
            existing_name = preferencePlist['System']['System']['HostName']
        except:
            # If we can't get the name, assign empty string for now
            existing_name = ''

        if auto_run:
            if component.get('use_serial', False):
                self.computerName = hardware_info.get('serial_number', 'UNKNOWN')
            else:
                self.computerName = existing_name
            self.theTabView.selectTabViewItem_(self.mainTab)
            self.workflowOnThreadPrep()
        else:
            if component.get('use_serial', False):
                self.computerNameInput.setStringValue_(hardware_info.get('serial_number', ''))
            elif component.get('prefix', None):
                self.computerNameInput.setStringValue_(component.get('prefix'))
            else:
                self.computerNameInput.setStringValue_(existing_name)

            # Switch to the computer name tab
            self.theTabView.selectTabViewItem_(self.computerNameTab)
            self.mainWindow.makeFirstResponder_(self.computerNameInput)

    @objc.IBAction
    def setComputerName_(self, sender):
        self.computerName = self.computerNameInput.stringValue()
        self.theTabView.selectTabViewItem_(self.mainTab)
        self.workflowOnThreadPrep()

    @objc.IBAction
    def restartButtonClicked_(self, sender):
        NSLog("Restart Button Clicked")
        self.restartToImagedVolume()

    def restartToImagedVolume(self):
        if self.restartAction == 'restart':
            cmd = ['/sbin/reboot']
        elif self.restartAction == 'shutdown':
            cmd = ['/sbin/shutdown', '-h', 'now']
        task = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        task.communicate()

    def openEndWorkflowPanel(self):
        label_string = "%s completed." % self.selectedWorkflow['name']
        alert = NSAlert.alertWithMessageText_defaultButton_alternateButton_otherButton_informativeTextWithFormat_(
            NSLocalizedString(label_string, None),
            NSLocalizedString(u"Restart", None),
            NSLocalizedString(u"Run another workflow", None),
            NSLocalizedString(u"Shutdown", None),
            NSLocalizedString(u"", None),)

        alert.beginSheetModalForWindow_modalDelegate_didEndSelector_contextInfo_(
            self.mainWindow, self, self.endWorkflowAlertDidEnd_returnCode_contextInfo_, objc.nil)

    @PyObjCTools.AppHelper.endSheetMethod
    def endWorkflowAlertDidEnd_returnCode_contextInfo_(self, alert, returncode, contextinfo):
        # -1 = Shutdown
        # 0 = another workflow
        # 1 = Restart

        if returncode == -1:
            # NSLog("You clicked %@ - shutdown", returncode)
            self.restartAction = 'shutdown'
            self.restartToImagedVolume()
        elif returncode == 1:
            # NSLog("You clicked %@ - restart", returncode)
            self.restartAction = 'restart'
            self.restartToImagedVolume()
        elif returncode == 0:
            # NSLog("You clicked %@ - another workflow", returncode)
            self.reloadVolumes()
            self.enableWorkflowViewControls()
            self.chooseImagingTarget_(None)
            # self.loadDataComplete()

    def enableAllButtons_(self, sender):
        self.cancelAndRestartButton.setEnabled_(True)
        self.runWorkflowButton.setEnabled_(True)

    def disableAllButtons_(self, sender):
        self.cancelAndRestartButton.setEnabled_(False)
        self.runWorkflowButton.setEnabled_(False)

    @objc.IBAction
    def runUtilityFromMenu_(self, sender):
        app_name = sender.title()
        app_path = os.path.join('/Applications/Utilities/', app_name + '.app')
        if os.path.exists(app_path):
            Utils.launchApp(app_path)

    def buildUtilitiesMenu(self):
        """
        Adds all applications in /Applications/Utilities to the Utilities menu
        """
        self.utilities_menu.removeAllItems()
        for item in os.listdir('/Applications/Utilities'):
            if item.endswith('.app'):
                item_name = os.path.splitext(item)[0]
                new_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    item_name, self.runUtilityFromMenu_, u'')
                new_item.setTarget_(self)
                self.utilities_menu.addItem_(new_item)

    def shakeWindow(self):
        shake = {'count': 1, 'duration': 0.3, 'vigor': 0.04}
        shakeAnim = Quartz.CAKeyframeAnimation.animation()
        shakePath = Quartz.CGPathCreateMutable()
        frame = self.mainWindow.frame()
        Quartz.CGPathMoveToPoint(shakePath, None, NSMinX(frame), NSMinY(frame))
        shakeLeft = NSMinX(frame) - frame.size.width * shake['vigor']
        shakeRight = NSMinX(frame) + frame.size.width * shake['vigor']
        for i in range(shake['count']):
            Quartz.CGPathAddLineToPoint(shakePath, None, shakeLeft, NSMinY(frame))
            Quartz.CGPathAddLineToPoint(shakePath, None, shakeRight, NSMinY(frame))
            Quartz.CGPathCloseSubpath(shakePath)
        shakeAnim._['path'] = shakePath
        shakeAnim._['duration'] = shake['duration']
        self.mainWindow.setAnimations_(NSDictionary.dictionaryWithObject_forKey_(shakeAnim, "frameOrigin"))
        self.mainWindow.animator().setFrameOrigin_(frame.origin)

    @objc.IBAction
    def showHelp_(self, sender):
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_("https://github.com/grahamgilbert/imagr/wiki"))
