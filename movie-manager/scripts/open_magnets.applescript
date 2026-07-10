on run argv
	set submittedCount to 0
	set scriptPath to POSIX path of (path to me)
	set scriptsDirectory to do shell script "/usr/bin/dirname " & quoted form of scriptPath
	set confirmHelper to scriptsDirectory & "/confirm_quark_download.swift"
	repeat with magnetLink in argv
		set linkText to magnetLink as text
		if linkText starts with "magnet:" then
			open location linkText
			do shell script "/usr/bin/swift " & quoted form of confirmHelper
			set submittedCount to submittedCount + 1
		end if
	end repeat
	display notification ("Submitted " & submittedCount & " Quark download(s)") with title "Movie Manager"
end run
