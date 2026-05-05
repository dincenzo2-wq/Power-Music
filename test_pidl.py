from win32com.shell import shell
import pythoncom
import os

def test():
    pythoncom.OleInitialize()
    abs_path = os.path.abspath(__file__)
    dir_path = os.path.dirname(abs_path)
    filename = os.path.basename(abs_path)
    
    dir_pidl, _ = shell.SHParseDisplayName(dir_path, 0)
    print("Got dir_pidl")
    
    # SHBindToObject needs parent, pidl, pbc, riid
    # Wait, SHBindToObject in pywin32 signature: shell.SHBindToObject(pidlFolder, pbc, riid)
    # Actually, we can use desktop.BindToObject
    desktop = shell.SHGetDesktopFolder()
    dir_folder = desktop.BindToObject(dir_pidl, None, shell.IID_IShellFolder)
    print("Got dir_folder")
    
    # ParseDisplayName
    eaten, rel_pidl, attr = dir_folder.ParseDisplayName(0, None, filename, 0)
    print("Got rel_pidl")
    
    data_obj = shell.SHCreateDataObject(dir_pidl, [rel_pidl], None, pythoncom.IID_IDataObject)
    print("Got data_obj")
    
if __name__ == "__main__":
    test()
