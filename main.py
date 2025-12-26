from pathlib import Path
from textual import events, on
from textual.widgets import TextArea, DirectoryTree, Input, Static
from textual.binding import Binding
from textual.app import App, ComposeResult
from textual.containers import HorizontalGroup, VerticalScroll, VerticalGroup
import asyncio
import ctypes

class Terminal(Static):
    def compose(self) -> ComposeResult:
        self.input = Input(placeholder="Enter shell command...")
        self.output = VerticalScroll()

        yield self.input
        yield self.output

    @on(Input.Submitted)
    async def handle_command_entered(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        self.output.mount(Static(f"> {cmd}"))
        
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()

        if stdout:
            self.output.mount(Static(f"{stdout.decode()}"))
        if stderr:
            self.output.mount(Static(f"{stderr.decode()}"))

class CodeEditor(TextArea, inherit_bindings=False):
    RESTRICTED_BINDINGS = [
        Binding('I', "move('up')"),
        Binding('J', "move('left')"),
        Binding('K', "move('down')"),
        Binding('L', "move('right')"),
        Binding('ctrl+j', "move('word_left')"),
        Binding('ctrl+l', "move('word_right')"),
        Binding(';', "move('line_end')"),
        Binding('H', "move('line_start')"),
        Binding('V', 'toggle_select'),
        Binding('U', 'delete_word_left'),
        Binding('O', 'delete_word_right'),
        Binding('ctrl+u', 'delete_to_start_of_line'),
        Binding('ctrl+o', 'delete_to_end_of_line_or_delete_line'),
        Binding('W', 'cursor_page_up'),
        Binding('S', 'cursor_page_down'),
        Binding('C', "insert_start_of_sel_lines('#')"),
        Binding('>', "insert_start_of_sel_lines('\t')"),
        Binding('G', 'goto'),
    ]

    BINDINGS = [
        Binding('backspace', 'delete_left'),
        Binding('ctrl+x', 'cut'),
        Binding('ctrl+c', 'copy'),
        Binding('ctrl+v', 'paste'),
        Binding('ctrl+z', 'undo'),
        Binding('ctrl+y', 'redo'),
        Binding('ctrl+s', 'save')

    ] + RESTRICTED_BINDINGS

    SELF_CLOSING = {
        '(': ')',
        '[': ']',
        '{': '}',
        '\'': '\'',
        '\"': '\"',
    }

    ACTIVE_BUFFERS = {}
    CURRENT_BUFFER_PATH = None
    OPTION_OPEN = False
    CMD_OPTION = ""
    GOTO_PAIRS = None

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        action_names = [binding.action.split('(')[0] for binding in self.RESTRICTED_BINDINGS]
        if (action in action_names) and self.OPTION_OPEN: # theoretically w/ this goto shouldn't work on the second press, but it does. if it works dont fix it
            return False
        return True

    def file_is_loaded(self) -> bool:
        if not self.CURRENT_BUFFER_PATH:
            return False

        if self.CURRENT_BUFFER_PATH not in self.ACTIVE_BUFFERS.keys(): # IDK why i wrote this but i did so i'll keep it lol
            return False

        return True

    @on(TextArea.Changed)
    def handle_text_change(self, event: TextArea.Changed) -> None:
        if not self.file_is_loaded():
            return

        if self.GOTO_PAIRS:
            with self.prevent(TextArea.Changed):
                self.text = self.ACTIVE_BUFFERS[self.CURRENT_BUFFER_PATH]['text']
            self.GOTO_PAIRS = None

        self.ACTIVE_BUFFERS[self.CURRENT_BUFFER_PATH]['text'] = self.text
        self.ACTIVE_BUFFERS[self.CURRENT_BUFFER_PATH]['saved'] = False
        self.border_title = "Unsaved"

    def action_goto(self) -> None:
        if self.CMD_OPTION.isdigit(): #goto line
            line_count = self.document.line_count
            target_line = min(int(self.CMD_OPTION)-1, line_count-1)
            target_location = (target_line, 0)
            self.move_cursor(location=target_location, center=True)
        elif self.CMD_OPTION.isalpha(): #goto word
            if not self.GOTO_PAIRS:
                self.move_cursor_relative(columns=-1)
                self.CMD_OPTION = ""
                return

            if self.CMD_OPTION not in self.GOTO_PAIRS.keys():
                self.move_cursor_relative(columns=1)
                self.CMD_OPTION = ""
                return

            target_location = self.GOTO_PAIRS[self.CMD_OPTION]
            self.move_cursor(location=target_location, center=True)

        self.CMD_OPTION = ""

    def goto_scramble(self, unscramble: bool) -> None:
        if unscramble:
            with self.prevent(TextArea.Changed):
                self.text = self.ACTIVE_BUFFERS[self.CURRENT_BUFFER_PATH].get('text', '')
            return

        cursor_row = self.cursor_location[0]
        replace_start = max(0, cursor_row - 10)
        replace_end = min(self.document.line_count - 1, cursor_row + 10)
        txt_range = self.get_text_range((replace_start, 0), (replace_end, 0)) + ' ' # this space is necessary for my spaghetti slop 
        alphabet = ('A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z') # no G b/c stuff i predict
        # this is 100% solvable with ASCII instead of whatever im doing but we ball anyway

        word_builder = ""
        word_num = 0
        new_text = ""

        self.GOTO_PAIRS = {}
        col_counter = 0
        pair_col = 0
        pair_row = replace_start

        for i in range(len(txt_range)): # I'm onto something.
            if txt_range[i].isspace():
                col_counter += 1

                if len(word_builder) > 1:
                    first_letter = alphabet[int(word_num/25)]
                    second_letter = alphabet[int(word_num)%25]
                    word_builder = first_letter + second_letter + word_builder[2:]
                    self.GOTO_PAIRS[first_letter + second_letter] = (pair_row, pair_col)

                if word_builder:
                    new_text += word_builder
                    word_num += 1

                if txt_range[i] == '\n':
                    pair_row += 1
                    pair_col = 0
                    col_counter = 0

                word_builder = ''
                new_text += txt_range[i]
                continue

            if not word_builder:
                pair_col = col_counter
            word_builder += txt_range[i]
            col_counter += 1

        with self.prevent(TextArea.Changed):
            self.replace(new_text, (replace_start, 0), (replace_end, 0))
        
    def action_save(self) -> None:
        if not self.file_is_loaded():
            return

        if not self.CURRENT_BUFFER_PATH: # life sucks this is just to suppress some random error that appears. I crack dudes but since nobody looks at this noone knows
            return

        text_to_save = self.ACTIVE_BUFFERS[self.CURRENT_BUFFER_PATH].get('text', '')
        with open(self.CURRENT_BUFFER_PATH, 'w') as f:
            f.write(text_to_save)

        self.ACTIVE_BUFFERS[self.CURRENT_BUFFER_PATH]['saved'] = True
        self.border_title = "Saved"
        self.notify('File saved.', timeout=3.0)

    def swap_file(self, path: Path) -> None:
        if path in self.ACTIVE_BUFFERS.keys():
            with self.prevent(TextArea.Changed):
                self.text = self.ACTIVE_BUFFERS[path].get('text', '')

            self.border_title = "Saved" if self.ACTIVE_BUFFERS[path]['saved'] else "Unsaved"
            self.CURRENT_BUFFER_PATH = path
            return 

        with open(path, 'r') as f:
            contents = f.read()
            with self.prevent(TextArea.Changed): # poop
                self.text = contents

            self.ACTIVE_BUFFERS[path] = {'text': contents, 'saved': True}
            self.CURRENT_BUFFER_PATH = path
            self.border_title = "Saved"

    def action_move(self, dir: str) -> None:
        match dir:
            case 'up':
                self.action_cursor_up(self.select)
            case 'left':
                self.action_cursor_left(self.select)
            case 'down':
                self.action_cursor_down(self.select)
            case 'right':
                self.action_cursor_right(self.select)
            case 'word_left':
                self.action_cursor_word_left(self.select)
            case 'word_right':
                self.action_cursor_word_right(self.select)
            case 'line_end':
                self.action_cursor_line_end(self.select)
            case 'line_start':
                self.action_cursor_line_start(self.select)

    def action_semicolon_end(self) -> None:
        self.action_cursor_line_end(False)
        self.insert(';')

    def action_insert_start_of_sel_lines(self, char: str) -> None:
        start = min(self.selection.start, self.selection.end)
        end = max(self.selection.start, self.selection.end)
        start_row = start[0]
        end_row = end[0]

        for row in range(start_row, end_row + 1):
            insert_pos = (row, 0)
            self.insert(char, location=insert_pos)

    def action_toggle_select(self) -> None: # because shift sucks for some reason?
        self.select = not self.select
  
    def cmd_mode(self) -> bool: # currently windows only
        return True if ctypes.WinDLL("User32.dll").GetKeyState(0x14) else False

    def cmd_mode_str(self) -> str:
        return "Command" if self.cmd_mode() else "Insert"
    
    def _on_key(self, event: events.Key):
        if self.cmd_mode():
            event.prevent_default()

            if self.OPTION_OPEN and event.character and event.character != 'G':
                self.CMD_OPTION += event.character 
            
            if event.character == 'G':
                self.OPTION_OPEN = not self.OPTION_OPEN
                with self.prevent(TextArea.Changed):
                    self.goto_scramble(not self.OPTION_OPEN)
            
            return

        if event.character in self.SELF_CLOSING.keys():
            self.insert(event.character + self.SELF_CLOSING[event.character])
            self.move_cursor_relative(columns=-1)
            event.prevent_default()

    def on_mount(self) -> None:
        self.select = False
        self.cursor_blink = False
        self.theme = 'vscode_dark'
    
class SubspaceApp(App):
    CSS = """
    #dirtree, #editor, #terminal {
        border: heavy gray;
        border-title-color: white;
        border-title-style: bold;
    }
    
    #dirtree {
        width: 0.3fr;
    }

    #editor {
        height: 0.7fr;
    }

    #terminal {
        height: 0.3fr;
    }
    """
    
    def compose(self) -> ComposeResult:
        self.editor: CodeEditor  = CodeEditor.code_editor(language='python', id='editor')

        with HorizontalGroup():
            yield DirectoryTree(path="", id="dirtree")
            with VerticalGroup():
                yield self.editor
                yield Terminal(id="terminal")

    @on(DirectoryTree.FileSelected)
    def handle_file_select(self, event: DirectoryTree.FileSelected) -> None:
        self.editor.swap_file(event.path)

    def on_mount(self) -> None:
        self.editor.border_title = "No file selected..."


if __name__ == "__main__":
    app = SubspaceApp()
    app.run()
