Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonwPath = fso.BuildPath(scriptDir, ".venv\Scripts\pythonw.exe")
mainPath = fso.BuildPath(scriptDir, "main.py")

If Not fso.FileExists(pythonwPath) Then
    message = "Python virtual environment was not found:" & vbCrLf
    message = message & pythonwPath & vbCrLf & vbCrLf
    message = message & "Please run these commands in the project folder first:" & vbCrLf
    message = message & "python -m venv .venv" & vbCrLf
    message = message & ".\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    MsgBox message, vbExclamation, "Desktop Translator"
    WScript.Quit 1
End If

If Not fso.FileExists(mainPath) Then
    MsgBox "Main program was not found:" & vbCrLf & mainPath, vbExclamation, "Desktop Translator"
    WScript.Quit 1
End If

shell.CurrentDirectory = scriptDir
shell.Run """" & pythonwPath & """ """ & mainPath & """", 0, False
