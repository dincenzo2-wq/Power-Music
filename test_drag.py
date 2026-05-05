from win32com.shell import shell
import pythoncom
import os

def test():
    files = [r"f:\Business Dropbox\Tran Vinh\Tài Nguyên Dựng Phim\Tài Nguyên Tổng Hợp\Workspace Editing\MusicOrganizer\music_organizer.py"]
    try:
        pythoncom.OleInitialize()
        # Get absolute pidls
        pidls = [shell.SHParseDisplayName(f, 0)[0] for f in files]
        print(f"Got {len(pidls)} pidls")
        
        # Create DataObject
        # SHCreateDataObject(pidlFolder, pidls, data_obj, iid)
        desktop_pidl = shell.SHGetSpecialFolderLocation(0, 0) # 0 = CSIDL_DESKTOP
        data_obj = shell.SHCreateDataObject(desktop_pidl, pidls, None, pythoncom.IID_IDataObject)
        print("Created DataObject successfully!")
        return True
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test()
