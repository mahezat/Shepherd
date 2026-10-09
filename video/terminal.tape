# Shepherd: a real run, recorded with VHS (charmbracelet/vhs).
Output terminal.mp4
Set Shell "bash"
Set FontSize 26
Set FontFamily "Courier Prime"
Set LineHeight 1.25
Set Width 1920
Set Height 1080
Set Padding 60
Set Theme { "name": "Shepherd Ledger", "background": "#2b2118", "foreground": "#efe6d2", "cursor": "#d9a441", "selection": "#4a3a2a", "black": "#2b2118", "red": "#e07a5f", "green": "#a3c585", "yellow": "#d9a441", "blue": "#9fb8cc", "magenta": "#d9a441", "cyan": "#c9b89a", "white": "#efe6d2", "brightBlack": "#8a7a62", "brightRed": "#e07a5f", "brightGreen": "#a3c585", "brightYellow": "#e8c069", "brightBlue": "#9fb8cc", "brightMagenta": "#e8c069", "brightCyan": "#c9b89a", "brightWhite": "#fffaf0" }
Set TypingSpeed 45ms

Hide
Type "cd /home/claude/shepherd && set -a && . /home/claude/.shepherd.env && set +a && export WANDB_ENTITY=maxmoud WANDB_PROJECT=shepherd WEAVE_PRINT_CALL_LINK=false PS1='\[\e[38;2;217;164;65m\]shepherd@fredon-nj \[\e[0m\]$ ' && clear" Enter
Sleep 500ms
Show

Type "ls clips/*.mp4 | wc -l    # our real coop clips" Sleep 300ms Enter
Sleep 1.5s
Type "python3 -m shepherd.agent 2>/dev/null | grep -vi weave" Sleep 400ms Enter
Wait+Screen@40s /report by/
Sleep 3s
Type "clear" Enter
Type "python3 -m shepherd.ask 'when was the last time a hen laid an egg?' 2>/dev/null | grep -vi weave" Sleep 400ms Enter
Wait+Screen@40s /answered by/
Sleep 4s
Type "python3 tests/test_rules.py 2>&1 | tail -1; python3 tests/test_ask.py" Sleep 300ms Enter
Sleep 3s
