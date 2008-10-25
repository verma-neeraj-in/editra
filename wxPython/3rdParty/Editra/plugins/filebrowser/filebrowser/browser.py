# -*- coding: utf-8 -*-
###############################################################################
# Name: browser.py                                                            #
# Purpose: UI portion of the FileBrowser Plugin                               #
# Author: Cody Precord <cprecord@editra.org>                                  #
# Copyright: (c) 2008 Cody Precord <staff@editra.org>                         #
# License: wxWindows License                                                  #
###############################################################################

"""
Provides a file browser panel and other UI components for Editra's
FileBrowser Plugin.

"""

__author__ = "Cody Precord <cprecord@editra.org>"
__svnid__ = "$Id$"
__revision__ = "$Revision$"

#-----------------------------------------------------------------------------#
# Imports
import os
import sys
import stat
import zipfile
import shutil
import subprocess
import threading
import wx

# Editra Library Modules
import ed_glob
import ed_msg
import ed_menu
import syntax.syntax
import util
from eclib import platebtn

# Local Imports
import FileInfo
import Trash

#-----------------------------------------------------------------------------#
# Globals
PANE_NAME = u'FileBrowser'
ID_BROWSERPANE = wx.NewId()
ID_FILEBROWSE = wx.NewId()

# Configure Platform specific commands
FILEMAN_CMD = util.GetFileManagerCmd()
if wx.Platform == '__WXMAC__':
    FILEMAN = 'Finder'
elif wx.Platform == '__WXMSW__':
    FILEMAN = 'Explorer'
else: # Other/Linux
    FILEMAN = FILEMAN_CMD.title()

def TrashString():
    """Get the trash description string"""
    if wx.Platform == '__WXMSW__':
        return _("Move to Recycle Bin")
    else:
        return _("Move to Trash")

_ = wx.GetTranslation
#-----------------------------------------------------------------------------#

ID_MARK_PATH = wx.NewId()
ID_OPEN_MARK = wx.NewId()
ID_REMOVE_MARK = wx.NewId()

class BrowserMenuBar(wx.Panel):
    """Creates a menubar with """

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, style=wx.NO_BORDER)

        # Attributes
        self._saved = ed_menu.EdMenu()
        self._rmpath = ed_menu.EdMenu()
        self._ids = list()  # List of ids of menu items
        self._rids = list() # List of remove menu item ids

        key = u'Ctrl'
        if wx.Platform == '__WXMAC__':
            key = u'Cmd'

        tt = wx.ToolTip(_("To open multiple files at once %s+Click to select "
                          "the desired files/folders then hit Enter to open "
                          "them all at once") % key)
        self.SetToolTip(tt)

        # Build Menus
        menu = ed_menu.EdMenu()
        menu.Append(ID_MARK_PATH, _("Save Selected Paths"))
        menu.AppendMenu(ID_OPEN_MARK, _("Jump to Saved Path"), self._saved)
        menu.AppendSeparator()
        menu.AppendMenu(ID_REMOVE_MARK, _("Remove Saved Path"), self._rmpath)

        # Button
        bmp = wx.ArtProvider.GetBitmap(str(ed_glob.ID_ADD_BM), wx.ART_MENU)
        self.menub = platebtn.PlateButton(self, bmp=bmp,
                                          style=platebtn.PB_STYLE_NOBG)
        self.menub.SetToolTipString(_("Pathmarks"))
        self.menub.SetMenu(menu)

        # Layout bar
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add((1, 1))
        men_sz = wx.BoxSizer(wx.HORIZONTAL)
        men_sz.Add((6, 6))
        men_sz.Add(self.menub, 0, wx.ALIGN_LEFT)
        sizer.Add(men_sz)
        sizer.Add((1, 1))
        self.SetSizer(sizer)

        # Event Handlers
        ed_msg.Subscribe(self.OnThemeChanged, ed_msg.EDMSG_THEME_CHANGED)
        self.Bind(wx.EVT_BUTTON, lambda evt: self.menub.ShowMenu(), self.menub)
        # Due to transparency issues dont do painting on gtk
        if wx.Platform != '__WXGTK__':
            self.Bind(wx.EVT_PAINT, self.OnPaint)

    def __del__(self):
        """Unsubscribe from messages"""
        ed_msg.Unsubscribe(self.OnThemeChanged)

    # XXX maybe change to list the more recently added items near the top
    def AddItem(self, label):
        """Add an item to the saved list, this also adds an identical 
        entry to the remove list so it can be removed if need be.

        """
        save_id = wx.NewId()
        self._ids.append(save_id)
        rem_id = wx.NewId()
        self._rids.append(rem_id)
        self._saved.Append(save_id, label)
        self._rmpath.Append(rem_id, label)

    def GetOpenIds(self):
        """Returns the ordered list of menu item ids"""
        return self._ids

    def GetRemoveIds(self):
        """Returns the ordered list of remove menu item ids"""
        return self._rids

    def GetItemText(self, item_id):
        """Retrieves the text label of the given item"""
        item = self.GetSavedMenu().FindItemById(item_id)
        if not item:
            item = self.GetRemoveMenu().FindItemById(item_id)

        if item:
            return item.GetLabel()
        else:
            return u''

    def GetRemoveMenu(self):
        """Returns the remove menu"""
        return self._rmpath

    def GetSavedMenu(self):
        """Returns the menu containg the saved items"""
        return self._saved

    def OnPaint(self, evt):
        """Paints the background of the menubar"""
        dc = wx.PaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        col1 = util.AdjustColour(wx.SystemSettings_GetColour(wx.SYS_COLOUR_3DFACE), -15)
        col2 = util.AdjustColour(wx.SystemSettings_GetColour(wx.SYS_COLOUR_3DFACE), 40)
        rect = self.GetRect()
        grad = gc.CreateLinearGradientBrush(0, 1, 0, rect.height, col2, col1)

        # Create the background path
        path = gc.CreatePath()
        path.AddRectangle(0, 0, rect.width - 0.5, rect.height - 0.5)

        gc.SetPen(wx.Pen(util.AdjustColour(col1, -20), 1))
        gc.SetBrush(grad)
        gc.DrawPath(path)

        evt.Skip()

    def OnThemeChanged(self, msg):
        """Update the buttons icon when the icon theme changes
        @param msg: Message Object

        """
        bmp = wx.ArtProvider.GetBitmap(str(ed_glob.ID_ADD_BM), wx.ART_MENU)
        self.menub.SetBitmap(bmp)
        self.menub.Refresh()

    def RemoveItemById(self, path_id):
        """Removes a given menu item from both the saved
        and removed lists using the id as a lookup.

        """
        o_ids = self.GetOpenIds()
        r_ids = self.GetRemoveIds()

        if path_id in r_ids:
            index = r_ids.index(path_id)
            self.GetRemoveMenu().Remove(path_id)
            self.GetSavedMenu().Remove(o_ids[index])
            self._rids.remove(path_id)
            del self._ids[index]

#-----------------------------------------------------------------------------#

class BrowserPane(wx.Panel):
    """Creates a filebrowser Pane"""
    ID_SHOW_HIDDEN = wx.NewId()

    def __init__(self, parent, id, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=wx.NO_BORDER):
        wx.Panel.__init__(self, parent, id, pos, size, style)
        
        # Attributes
        self._mw = parent
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        filters = "".join(syntax.syntax.GenFileFilters())
        self._menbar = BrowserMenuBar(self)
        self._browser = FileBrowser(self, ID_FILEBROWSE, 
                                    dir=wx.GetHomeDir(), 
                                    size=(200, -1),
                                    style=wx.DIRCTRL_SHOW_FILTERS | 
                                          wx.DIRCTRL_EDIT_LABELS | 
                                          wx.BORDER_SUNKEN,
                                    filter=filters)
        self._config = PathMarkConfig(ed_glob.CONFIG['CACHE_DIR'])
        for item in self._config.GetItemLabels():
            self._menbar.AddItem(item)
        self._showh_cb = wx.CheckBox(self, self.ID_SHOW_HIDDEN, 
                                     _("Show Hidden Files"))
        self._showh_cb.SetValue(False)
        if wx.Platform == '__WXMAC__':
            self._showh_cb.SetWindowVariant(wx.WINDOW_VARIANT_SMALL)

        #---- Add Menu Items ----#
        viewm = self._mw.GetMenuBar().GetMenuByName("view")
        self._mi = viewm.InsertAlpha(ID_FILEBROWSE, _("File Browser"), 
                                     _("Open File Browser Sidepanel"),
                                     wx.ITEM_CHECK,
                                     after=ed_glob.ID_PRE_MARK)

        # Layout Pane
        self._sizer.AddMany([(self._menbar, 0, wx.EXPAND),
                             (self._browser, 1, wx.EXPAND),
                             ((2, 2))])
        cb_sz = wx.BoxSizer(wx.HORIZONTAL)
        cb_sz.Add((4, 4))
        cb_sz.Add(self._showh_cb, 0, wx.ALIGN_LEFT)
        self._sizer.Add(cb_sz, 0, wx.ALIGN_LEFT)
        self._sizer.Add((3, 3))
        self.SetSizer(self._sizer)

        # Event Handlers
        self.Bind(wx.EVT_CHECKBOX, self.OnCheck)
        self.Bind(wx.EVT_MENU, self.OnMenu)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

        # Messages
        ed_msg.Subscribe(self.OnUpdateFont, ed_msg.EDMSG_DSP_FONT)

    def __del__(self):
        """Save the config before we get destroyed"""
        self._config.Save()
        ed_msg.Unsubscribe(self.OnUpdateFont)

    def GetMainWindow(self):
        """Get the MainWindow that owns this panel"""
        return self._mw

    def OnCheck(self, evt):
        """Toggles visibility of hidden files on and off"""
        e_id = evt.GetId()
        if e_id == self.ID_SHOW_HIDDEN:
            style = self._browser.GetTreeStyle()
            self._browser.SetTreeStyle(wx.TR_SINGLE)
            self._browser.Refresh()
            self._browser.ShowHidden(self._showh_cb.GetValue())
            self._browser.SetTreeStyle(style)
            self._browser.Refresh()
        else:
            evt.Skip()

    # TODO after a jump the window should be properly rescrolled
    #      to have the jumped-to path at the top when possible
    def OnMenu(self, evt):
        """Handles the events associated with adding, opening,
        and removing paths in the menubars menus.

        """
        e_id = evt.GetId()
        o_ids = self._menbar.GetOpenIds()
        d_ids = self._menbar.GetRemoveIds()
        if e_id == ID_MARK_PATH:
            items = self._browser.GetPaths()
            for item in items:
                self._menbar.AddItem(item)
                self._config.AddPathMark(item, item)
                self._config.Save()
        elif e_id in o_ids:
            pmark = self._menbar.GetItemText(e_id)
            path = self._config.GetPath(pmark)
            self._browser.ExpandPath(path)
            self._browser.SetFocus()
        elif e_id in d_ids:
            plabel = self._menbar.GetItemText(e_id)
            self._menbar.RemoveItemById(e_id)
            self._config.RemovePathMark(plabel)
            self._config.Save()
        else:
            evt.Skip()

    def OnPaint(self, evt):
        """Paints the background of the panel"""
        dc = wx.PaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        col1 = util.AdjustColour(wx.SystemSettings_GetColour(wx.SYS_COLOUR_3DFACE), -15)
        col2 = util.AdjustColour(wx.SystemSettings_GetColour(wx.SYS_COLOUR_3DFACE), 40)
        rect = self.GetRect()
        x = 0
        y = rect.height - (self._showh_cb.GetSize()[1] + 6)
        grad = gc.CreateLinearGradientBrush(x, y, x, 
                                            y + self._showh_cb.GetSize()[1] + 6,
                                            col2, col1)

        # Create the background path
        path = gc.CreatePath()
        path.AddRectangle(x, y, rect.width - 0.5, 
                          self._showh_cb.GetSize()[1] + 6)

        gc.SetPen(wx.Pen(util.AdjustColour(col1, -20), 1))
        gc.SetBrush(grad)
        gc.DrawPath(path)

        evt.Skip()

    def OnShowBrowser(self, evt):
        """Shows the filebrowser"""
        if evt.GetId() == ID_FILEBROWSE:
            mgr = self._mw.GetFrameManager()
            pane = mgr.GetPane(PANE_NAME)
            if pane.IsShown():
                pane.Hide()
            else:
                pane.Show()
                cbuff = self._mw.GetNotebook().GetCurrentCtrl()
                path = cbuff.GetFileName()
                if path:
                    self._browser.GotoPath(path)
            mgr.Update()
        else:
            evt.Skip()

    def OnUpdateFont(self, msg):
        """Update the ui font when a message comes saying to do so."""
        font = msg.GetData()
        if isinstance(font, wx.Font) and not font.IsNull():
            for child in (self, self._browser, self._browser.GetTreeCtrl()):
                if hasattr(child, 'SetFont'):
                    child.SetFont(font)

    def OnUpdateMenu(self, evt):
        """UpdateUI handler for the panels menu item, to update the check
        mark.
        @param evt: wx.UpdateUIEvent

        """
        pane = self._mw.GetFrameManager().GetPane(PANE_NAME)
        evt.Check(pane.IsShown())

#-----------------------------------------------------------------------------#
# Menu Id's
ID_EDIT = wx.NewId()
ID_OPEN = wx.NewId()
ID_REVEAL = wx.NewId()
ID_GETINFO = wx.NewId()
ID_RENAME = wx.NewId()
ID_NEW_FOLDER = wx.NewId()
ID_NEW_FILE = wx.NewId()
ID_DELETE = wx.NewId()
ID_DUPLICATE = wx.NewId()
ID_ARCHIVE = wx.NewId()

class FileBrowser(wx.GenericDirCtrl):
    """Custom directory control for displaying and managing files"""
    def __init__(self, parent, id, dir=u'', pos=wx.DefaultPosition,
                 size=wx.DefaultSize,
                 style=wx.DIRCTRL_SHOW_FILTERS|wx.DIRCTRL_EDIT_LABELS,
                 filter=wx.EmptyString, defaultFilter=0):
        wx.GenericDirCtrl.__init__(self, parent, id, dir, pos, 
                                   size, style, filter, defaultFilter)

        # Attributes
        self._tree = self.GetTreeCtrl()
        self._treeId = 0                # id of TreeItem that was last rclicked
        self._fmenu = self._MakeMenu()
        self._drag_img = None
        
        # Set custom styles
        self._tree.SetWindowStyle(self._tree.GetWindowStyle() | wx.TR_MULTIPLE)
        self._tree.Refresh()
        self._imglst = self._tree.GetImageList()
        self._SetupIcons()

        # Event Handlers
        self.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.OnOpen)
        self.Bind(wx.EVT_TREE_ITEM_RIGHT_CLICK, self.OnContext)
        self.Bind(wx.EVT_MENU, self.OnMenu)
        ed_msg.Subscribe(self.OnThemeChanged, ed_msg.EDMSG_THEME_CHANGED)
        ed_msg.Subscribe(self.OnPageChange, ed_msg.EDMSG_UI_NB_CHANGED)
#        self.Bind(wx.EVT_TREE_BEGIN_DRAG, self.OnDragStart)
#        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnDragging)
#        self.Bind(wx.EVT_TREE_END_DRAG, self.OnDragEnd)

    def __del__(self):
        """Unsubscribe from messages"""
        ed_msg.Unsubscribe(self.OnPageChange)
        ed_msg.Unsubscribe(self.OnThemeChanged)

    def _SetupIcons(self):
        """If a custom theme is in use by Editra set the icons of the
        directory control to match.

        """
        # HACK if the GenericDirCtrl ever changes the order of the images used 
        #      in it this will have to be updated accordingly
        ids = [ed_glob.ID_FOLDER, ed_glob.ID_OPEN, ed_glob.ID_COMPUTER, 
               ed_glob.ID_HARDDISK, ed_glob.ID_CDROM, ed_glob.ID_FLOPPY, 
               ed_glob.ID_USB, ed_glob.ID_FILE, ed_glob.ID_BIN_FILE]

        for idx, art in enumerate(ids):
            bmp = wx.ArtProvider.GetBitmap(str(art), wx.ART_MENU)
            if bmp.IsOk():
                self._imglst.Replace(idx, bmp)

    def _MakeMenu(self):
        """Setup the context menu"""
        menu = wx.Menu()

        # MenuItems
        items = [(ID_EDIT, _("Edit"), None),
                 (ID_OPEN, _("Open with " + FILEMAN), ed_glob.ID_OPEN),
                 (ID_REVEAL, _("Reveal in " + FILEMAN), None),
                 (wx.ID_SEPARATOR, '', None),
                 (ID_MARK_PATH, _("Bookmark Selected Path(s)"),
                  ed_glob.ID_ADD_BM),
                 (wx.ID_SEPARATOR, '', None),
                 (ID_GETINFO, _("Get Info"), None),
                 (ID_RENAME, _("Rename"), None),
                 (wx.ID_SEPARATOR, '', None),
                 (ID_NEW_FOLDER, _("New Folder"), ed_glob.ID_FOLDER),
                 (ID_NEW_FILE, _("New File"), ed_glob.ID_NEW),
                 (wx.ID_SEPARATOR, '', None),
                 (ID_DUPLICATE, _("Duplicate"), None),
                 (ID_ARCHIVE, _("Create Archive of \"%s\"") % '', None),
                 (wx.ID_SEPARATOR, '', None),
                 (ID_DELETE, TrashString(), ed_glob.ID_DELETE),
                ]

        for item in items:
            mitem = wx.MenuItem(menu, item[0], item[1])
            if item[2] is not None:
                bmp = wx.ArtProvider.GetBitmap(str(item[2]), wx.ART_MENU)
                mitem.SetBitmap(bmp)

            menu.AppendItem(mitem)
        return menu

    def _SCommand(self, cmd, *args):
        """Run a tree command that requires de-hacking the windows style
        before running. (Some commands raise errors on msw if the style is
        not set back to TR_SINGLE before calling it.
        @param cmd: self.METHOD
        @keyword args: args to pass to command

        """
        style = self.GetTreeStyle()
        self.SetTreeStyle(wx.TR_SINGLE)
        self.Refresh()
        rval = cmd(*args)
        self.SetTreeStyle(style)
        self.Refresh()
        return rval

    def GetItemPath(self, itemId):
        """Get and return the path of the given item id
        @param itemId: TreeItemId
        @return: string

        """
        root = self._tree.GetRootItem()
        start = itemId
        atoms = [itemId]
        while self._tree.GetItemParent(start) != root:
            atoms.append(self._tree.GetItemParent(start))
            start = atoms[-1]

        atoms.reverse()
        path = list()
        for atom in atoms:
            path.append(self._tree.GetItemText(atom))

        if wx.Platform == '__WXMSW__':
            r_txt = u''
        else:
            if wx.Platform == '__WXGTK__':
                if path[0].lower() == 'home directory':
                    path[0] = wx.GetHomeDir()
                elif path[0].lower() == 'desktop':
                    path.insert(0, wx.GetHomeDir())
                else:
                    pass

            if wx.Platform == '__WXMAC__':
                if path[0] != "/":
                    if path == 'Macintosh HD':
                        path.pop(0)
                    else:
                        path.insert(0, 'Volumes')

            r_txt = os.path.sep
        return r_txt + os.sep.join(path)

    def GetPaths(self):
        """Gets a list of abs paths of the selected items"""
        ret_val = list()
        for leaf in self._tree.GetSelections():
            ret_val.append(self.GetItemPath(leaf))
        return ret_val

    def GetScrollRange(self, orient=wx.VERTICAL):
        """Returns the scroll range of the tree control"""
        return self._tree.GetScrollRange(orient)

    def GetTreeStyle(self):
        """Returns the trees current style"""
        return self._tree.GetWindowStyle()

    def GotoPath(self, path):
        """Move the selection to the given path
        @param path: string:

        """
        style = self.GetTreeStyle()
        self.SetTreeStyle(wx.TR_SINGLE)
        self.Refresh()
        self.SetPath(path)
        self.SetTreeStyle(style)
        self.Refresh()        

    def OnContext(self, evt):
        """Show the popup context menu"""
        self._fmenu.Destroy()
        self._fmenu = self._MakeMenu()
        self._treeId = evt.GetItem()
        path = self.GetItemPath(self._treeId)
        mitem = self._fmenu.FindItemById(ID_ARCHIVE)
        if mitem != wx.NOT_FOUND:
            mitem.SetText(_("Create Archive of \"%s\"") % \
                          path.split(os.path.sep)[-1])

        for item in (ID_DUPLICATE,):
            self._fmenu.Enable(item, len(self._tree.GetSelections()) == 1)
        self.PopupMenu(self._fmenu)

    def OnMenu(self, evt):
        """Handle the context menu events for performing
        filesystem operations

        """
        e_id = evt.GetId()
        path = self.GetItemPath(self._treeId)
        paths = self.GetPaths()
        ok = (False, '')
        if e_id == ID_EDIT:
            self.OpenFiles(paths)
        elif e_id == ID_OPEN:
            worker = OpenerThread(paths)
            worker.start()
        elif e_id == ID_REVEAL:
            worker = OpenerThread([os.path.dirname(fname) for fname in paths])
            worker.start()
        elif e_id == ID_GETINFO:
            last = None
            for fname in paths:
                info = FileInfo.FileInfoDlg(self.GetTopLevelParent(), fname)
                if last is None:
                    info.CenterOnParent()
                else:
                    lpos = last.GetPosition()
                    info.SetPosition((lpos[0] + 14, lpos[1] + 14))
                info.Show()
                last = info
        elif e_id == ID_RENAME:
            self._tree.EditLabel(self._treeId)
        elif e_id == ID_NEW_FOLDER:
            ok = util.MakeNewFolder(path, _("Untitled_Folder"))
        elif e_id == ID_NEW_FILE:
            ok = util.MakeNewFile(path, _("Untitled_File") + ".txt")
        elif e_id == ID_DUPLICATE:
            for fname in paths:
                ok = DuplicatePath(fname)
        elif e_id == ID_ARCHIVE:
            ok = MakeArchive(path)
        elif e_id == ID_DELETE:
            Trash.moveToTrash(paths)
            ok = (True, os.path.dirname(path))
        else:
            evt.Skip()
            return

        if e_id in (ID_NEW_FOLDER, ID_NEW_FILE, ID_DUPLICATE, ID_ARCHIVE,
                    ID_DELETE):
            if ok[0]:
                self.ReCreateTree()
                self._SCommand(self.SetPath, ok[1])

    def OnOpen(self, evt):
        """Handles item activations events. (i.e double clicked or 
        enter is hit) and passes the clicked on file to be opened in 
        the notebook.

        """
        files = self.GetPaths()
        item = self._SCommand(self.GetPath)
        if os.path.isdir(item):
            # Unlike Mac/Gtk, need to skip the event here to allow for
            # expanding paths with double clicks. This however disables the
            # ability to use Return as a key for expanding. It also doesn't
            # seem to be possible to tell whether the activation event was
            # caused by a double click or a key sequence.
            if wx.Platform == '__WXMSW__':
                evt.Skip()
            else:
                if self.IsExpanded(item):
                    self.Collapse(item)
                else:
                    self.ExpandPath(item)
            return
        else:
            files = [ fname for fname in files if not os.path.isdir(fname) ]
        self.OpenFiles(files)

    def OnPageChange(self, msg):
        """Syncronize selection with the notebook page changes
        @param msg: MessageObject
        @todo: check if message is from a page closing and avoid updates

        """
        
        nbdata = msg.GetData()
        page = nbdata[0].GetPage(nbdata[1])
        path = page.GetFileName()
        if path:
            self.GotoPath(path)

    def OnThemeChanged(self, msg):
        """Update the icons when the icon theme has changed
        @param msg: Message Object

        """
        self._SetupIcons()
        self._tree.Refresh()

    def OpenFiles(self, files):
        """Open the list of files in Editra for editing
        @param files: list of file names

        """
        to_open = list()
        for fname in files:
            try:
                res = os.stat(fname)[0]
                if stat.S_ISREG(res) or stat.S_ISDIR(res):
                    to_open.append(fname)
            except (IOError, OSError), msg:
                util.Log("[filebrowser][err] %s" % str(msg))

        win = wx.GetApp().GetActiveWindow()
        if win:
            win.GetNotebook().OnDrop(to_open)

      # TODO implement drag and drop from the control to the editor
#    def OnDragStart(self, evt):
#        """Start dragging a file from the tree"""
#        item = self._tree.GetSelection()
#        img = self._imglst.GetBitmap(self._tree.GetItemImage(item))
#        lbl = self._tree.GetItemText(item)
#        fdo = wx.FileDataObject()
#        fdo.AddFile(self.GetPath())
#        self._drag_img = FileDragImage(self._tree, lbl, img, fdo)
#        mw = self.GetParent().GetMainWindow()
#        self._drag_img.BeginDrag(wx.GetMousePosition(), self,
#                                 rect=mw.GetClientRect())
#        self._drag_img.Show()
#        self._drag_img.Move(wx.GetMousePosition())

#    def OnDragging(self, evt):
#        """Move the drag image"""
#        if evt.Dragging() and self._drag_img is not None:
#            self._drag_img.Move(evt.GetPosition())#wx.GetMousePosition())
#        elif self._drag_img is not None and evt.LeftUp():
#            print "LEFTUP"
#            self._drag_img.EndDrag()
#            self._drag_img.Destroy()
#            self._drag_img = None
#        else:
#            evt.Skip()

#    def OnDragEnd(self, evt):
#        """End the drag"""
#        print "END DRAG"
#        if self._drag_img is not None:
#            self._drag_img.EndDrag()
#            self._drag_img.Destroy()
#            self._drag_img = None
#        else:
#            evt.Skip()

#        evt.Skip()

#     def SelectPath(self, path):
#         """Selects the given path"""
#         parts = path.split(os.path.sep)
#         root = self._tree.GetRootItem()
#         rtxt = self._tree.GetItemText(root)
#         item, cookie = self._tree.GetFirstChild(root)
#         while item:
#             if self._tree.ItemHasChildren(item):
#                 i_txt = self._tree.GetItemText(item)
#                 print i_txt
#                 item, cookie = self._tree.GetFirstChild(item)
#                 continue
#             else:
#                 i_txt = self._tree.GetItemText(item)
#                 print i_txt
#             item, cookie = self._tree.GetNextChild(item, cookie)

    def SetTreeStyle(self, style):
        """Sets the style of directory controls tree"""
        self._tree.SetWindowStyle(style)

#-----------------------------------------------------------------------------#

# TODO maybe switch to storing this info in the user profile instead of
#      managing it here.
class PathMarkConfig(object):
    """Manages the saving of pathmarks to make them usable from
    one session to the next.

    """
    CONFIG_FILE = u'pathmarks'

    def __init__(self, pname):
        """Creates the config object, the pname parameter
        is the base path to store the config file at on write.

        """
        object.__init__(self)

        # Attributes
        self._base = os.path.join(pname, self.CONFIG_FILE)
        self._pmarks = dict()

        self.Load()

    def AddPathMark(self, label, path):
        """Adds a label and a path to the config"""
        self._pmarks[label.strip()] = path.strip()

    def GetItemLabels(self):
        """Returns a list of all the item labels in the config"""
        return self._pmarks.keys()

    def GetPath(self, label):
        """Returns the path associated with a given label"""
        return self._pmarks.get(label, u'')

    def Load(self):
        """Loads the configuration data into the dictionary"""
        file_h = util.GetFileReader(self._base)
        if file_h != -1:
            lines = file_h.readlines()
            file_h.close()
        else:
            return False

        for line in lines:
            vals = line.strip().split(u"=")
            if len(vals) != 2:
                continue
            if os.path.exists(vals[1]):
                self.AddPathMark(vals[0], vals[1])
        return True

    def RemovePathMark(self, pmark):
        """Removes a path mark from the config"""
        if self._pmarks.has_key(pmark):
            del self._pmarks[pmark]

    def Save(self):
        """Writes the config out to disk"""
        file_h = util.GetFileWriter(self._base)
        if file_h == -1:
            return False

        for label in self._pmarks:
            file_h.write(u"%s=%s\n" % (label, self._pmarks[label]))
        file_h.close()
        return True

#-----------------------------------------------------------------------------#
# Utilities
def DuplicatePath(path):
    """Create a copy of the item at the end of the given path. The item
    will be created with a name in the form of Dirname_Copy for directories
    and FileName_Copy.extension for files.
    @param path: path to duplicate
    @return: Tuple of (success?, filename OR Error Message)

    """
    head, tail = os.path.split(path)
    if os.path.isdir(path):
        name = util.GetUniqueName(head, tail + "_Copy")
        copy = shutil.copytree
    else:
        tmp = [ part for part in tail.split('.') if len(part) ]
        if tail.startswith('.'):
            tmp[0] = "." + tmp[0]
            if '.' not in tail[1:]:
                tmp[0] = tmp[0] + "_Copy"
            else:
                tmp.insert(-1, "_Copy.")

            tmp = ''.join(tmp)
        else:
            tmp = '.'.join(tmp[:-1]) + "_Copy." + tmp[-1]

        if len(tmp) > 1:
            name = util.GetUniqueName(head, tmp)
        copy = shutil.copy2

    try:
        copy(path, name)
    except Exception, msg:
        return (False, str(msg))

    return (True, name)

def MakeArchive(path):
    """Create a Zip archive of the item at the end of the given path
    @param path: full path to item to archive
    @return: Tuple of (success?, file name OR Error Message)
    @rtype: (bool, str)
    @todo: support for zipping multiple paths

    """
    dname, fname = os.path.split(path)
    ok = True
    name = ''
    if dname and fname:
        name = util.GetUniqueName(dname, fname + ".zip")
        files = list()
        cwd = os.getcwd()
        head = dname
        try:
            try:
                os.chdir(dname)
                if os.path.isdir(path):
                    for dpath, dname, fnames in os.walk(path):
                        files.extend([ os.path.join(dpath, fname).\
                                       replace(head, '', 1).\
                                       lstrip(os.path.sep) 
                                       for fname in fnames])

                zfile = zipfile.ZipFile(name, 'w', compression=zipfile.ZIP_DEFLATED)
                for fname in files:
                    zfile.write(fname.encode(sys.getfilesystemencoding()))
            except Exception, msg:
                ok = False
                name = str(msg)
        finally:
            zfile.close()
            os.chdir(cwd)

    return (ok, name)

#-----------------------------------------------------------------------------#

class OpenerThread(threading.Thread):
    """Job runner thread for opening files with the systems filemanager"""
    def __init__(self, files):
        self._files = files
        threading.Thread.__init__(self)

    def run(self):
        """Do the work of opeing the files"""
        for fname in self._files:
            subprocess.call([FILEMAN_CMD, fname])

#-----------------------------------------------------------------------------#

class FileDragImage(wx.DragImage):
    def __init__(self, treeCtrl, lbl, img, fdo):
        """Create the drag image
        @param treeCtrl: Tree control drag started from
        @param lbl: drag image label
        @param img: file image

        """
        bmp = self.MakeBitmap(treeCtrl, lbl, img)
        wx.DragImage.__init__(self, bmp, wx.StockCursor(wx.CURSOR_COPY_ARROW))

    def MakeBitmap(self, treeCtrl, lbl, img):
        """Draw and create the drag image
        @param treeCtrl: tree control drag started from
        @param lbl: label to draw
        @param img: image to draw

        """
        memory = wx.MemoryDC()

        # Calculate Sizes
        img_sz = img.GetSize()
        txt_sz = treeCtrl.GetTextExtent(lbl)
        bitmap = wx.EmptyBitmap(img_sz[0] + 7 + txt_sz[0],
                                max(img_sz[1], txt_sz[1]) + 2)
        memory.SelectObject(bitmap)

        if wx.Platform == '__WXMAC__':
            memory.SetBackground(wx.TRANSPARENT_BRUSH)
        else:
            backcolour = treeCtrl.GetBackgroundColour()
            r, g, b = int(backcolour.Red()), int(backcolour.Green()), int(backcolour.Blue())
            backcolour = ((r >> 1) + 20, (g >> 1) + 20, (b >> 1) + 20)
            backcolour = wx.Colour(backcolour[0], backcolour[1], backcolour[2])
            memory.SetBackground(wx.Brush(backcolour))

        memory.SetBackgroundMode(wx.TRANSPARENT)
        memory.SetFont(treeCtrl.GetFont())
        memory.SetTextForeground(treeCtrl.GetForegroundColour())
        memory.Clear()

        memory.DrawBitmap(img, 2, 1, True)

        textrect = wx.Rect(2 + img_sz[1] + 3, 2, txt_sz[0], txt_sz[1])
        memory.DrawLabel(lbl, textrect)

        memory.SelectObject(wx.NullBitmap)

        # Gtk and Windows unfortunatly don't do so well with transparent
        # drawing so this hack corrects the image to have a transparent
        # background.
        if wx.Platform != '__WXMAC__':
            timg = bitmap.ConvertToImage()
            if not timg.HasAlpha():
                timg.InitAlpha()
            for y in xrange(timg.GetHeight()):
                for x in xrange(timg.GetWidth()):
                    pix = wx.Colour(timg.GetRed(x, y),
                                    timg.GetGreen(x, y),
                                    timg.GetBlue(x, y))
                    if pix == self._backgroundColour:
                        timg.SetAlpha(x, y, 0)
            bitmap = timg.ConvertToBitmap()
        return bitmap
