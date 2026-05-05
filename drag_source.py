import os
import ctypes
import pythoncom
import win32con
import win32com.server.util
from win32com.shell import shell, shellcon
import win32api

# OLE Constants
DRAGDROP_S_DROP = 0x00040100
DRAGDROP_S_CANCEL = 0x00040101
DRAGDROP_S_USEDEFAULTCURSORS = 0x00040102
DROPEFFECT_NONE = 0
DROPEFFECT_COPY = 1
DROPEFFECT_MOVE = 2
DROPEFFECT_LINK = 4

class DropSource:
    _com_interfaces_ = [pythoncom.IID_IDropSource]
    _public_methods_ = ['QueryContinueDrag', 'GiveFeedback']
    
    def __init__(self, feedback_cb=None):
        self.feedback_cb = feedback_cb

    def QueryContinueDrag(self, fEscapePressed, grfKeyState):
        if fEscapePressed:
            return DRAGDROP_S_CANCEL
            
        # Instead of relying only on grfKeyState, we also check the physical state
        # VK_LBUTTON is 0x01
        left_button_down = win32api.GetKeyState(0x01) < 0
        if not left_button_down:
            return DRAGDROP_S_DROP
            
        return 0 # S_OK

    def GiveFeedback(self, dwEffect):
        if self.feedback_cb:
            try:
                self.feedback_cb()
            except:
                pass
        return DRAGDROP_S_USEDEFAULTCURSORS

def start_drag(filenames, feedback_cb=None):
    try:
        abs_paths = [os.path.abspath(f) for f in filenames if os.path.exists(f)]
        if not abs_paths:
            print("DEBUG: No valid files to drag")
            return 0
            
        # Ensure all files are in the same directory for the shell data object
        dir_path = os.path.dirname(abs_paths[0])
        
        # 1. Get the parent folder PIDL
        dir_pidl, _ = shell.SHParseDisplayName(dir_path, 0)
        
        # 2. Get the IShellFolder interface for the parent directory
        desktop = shell.SHGetDesktopFolder()
        dir_folder = desktop.BindToObject(dir_pidl, None, shell.IID_IShellFolder)
        
        # 3. Get relative PIDLs for all files
        rel_pidls = []
        for p in abs_paths:
            filename = os.path.basename(p)
            try:
                # ParseDisplayName(hwnd, pbc, name, attr) -> (eaten, pidl, attr)
                eaten, rel_pidl, attr = dir_folder.ParseDisplayName(0, None, filename, 0)
                rel_pidls.append(rel_pidl)
            except Exception as e:
                print(f"DEBUG: Failed to get rel PIDL for {filename}: {e}")
                
        if not rel_pidls:
            print("DEBUG: No relative PIDLs generated")
            return 0

        # 4. Create the DataObject EXACLTY like Explorer does
        # SHCreateDataObject(pidlFolder, apidl, pdtInner, riid)
        data_obj = shell.SHCreateDataObject(dir_pidl, rel_pidls, None, pythoncom.IID_IDataObject)
        
        # 5. Wrap DropSource
        ds_instance = DropSource(feedback_cb=feedback_cb)
        drop_source = win32com.server.util.wrap(ds_instance, pythoncom.IID_IDropSource)
        
        print(f"DEBUG: Starting Perfect Shell Drag for {len(abs_paths)} files...")
        res = pythoncom.DoDragDrop(
            data_obj, 
            drop_source, 
            DROPEFFECT_COPY | DROPEFFECT_MOVE | DROPEFFECT_LINK
        )
        print(f"DEBUG: Drag completed with result: {res}")
        return res
        
    except Exception as e:
        print(f"DEBUG: Drag and drop error: {e}")
        import traceback
        traceback.print_exc()
        return 0
