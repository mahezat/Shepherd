# Shepherd: a real run, recorded with VHS (charmbracelet/vhs).
Output terminal.mp4
Set Shell "bash"
Set FontSize 30
Set Width 1920
Set Height 1080
Set Padding 60
Set Theme { "name": "Shepherd", "background": "#0d1510", "foreground": "#e6eee3", "cursor": "#e2b448", "selection": "#26362c", "black": "#0d1510", "red": "#f07a62", "green": "#6cc488", "yellow": "#e2b448", "blue": "#9db0a2", "magenta": "#e8a94a", "cyan": "#9db0a2", "white": "#e6eee3", "brightBlack": "#56655a", "brightRed": "#f07a62", "brightGreen": "#6cc488", "brightYellow": "#e2b448", "brightBlue": "#9db0a2", "brightMagenta": "#e8a94a", "brightCyan": "#9db0a2", "brightWhite": "#ffffff" }
Set TypingSpeed 45ms

Hide
Type "cd /home/claude/shepherd && set -a && . /home/claude/.shepherd.env && set +a && export WANDB_ENTITY=maxmoud WANDB_PROJECT=shepherd WEAVE_PRINT_CALL_LINK=false PS1='\[\e[38;2;226;180;72m\]shepherd \[\e[0m\]$ ' && clear" Enter
Sleep 500ms
Show

Type "ls clips/*.mp4 | wc -l    # our real coop clips" Sleep 300ms Enter
Sleep 1.5s
Type "python3 -m shepherd.agent 2>/dev/null | grep -vi weave" Sleep 400ms Enter
Wait+Screen@40s /report by/
Sleep 3s
Type "python3 tests/test_rules.py 2>&1 | tail -3" Sleep 300ms Enter
Sleep 3s
