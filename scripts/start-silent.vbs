Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "D:\AURA\Aura"
sh.Environment("Process")("AURA_DATA") = "D:/AURA/data"
sh.Environment("Process")("OLLAMA_MODELS") = "D:\AURA\ollama-models"
sh.Run "cmd /c ""D:\AURA\Aura\scripts\launch-aura.bat""", 0, False
