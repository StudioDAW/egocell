import gi
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk
import cairo
from typing import List, Dict, Literal
import math
from cells import COLS, ROWS, CHARS, cells, columns, rows
import cell_types

CELL_W = 100
CELL_H = 20
MIN_SCALE = 0.2
MAX_SCALE = 5.0

formula_globals = {}
imports = [__builtins__, cell_types, math]
for i in imports: formula_globals.update({k: getattr(i, k) for k in dir(i) if not k.startswith("_")})
def run(expression):
    return eval(expression, formula_globals, cells)


class Sheet(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.window = window

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("...")
        self.entry.set_editable(True)
        self.entry.connect("activate", self.on_edit)

        key_controller = Gtk.EventControllerKey.new()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self.on_input)
        self.entry.add_controller(key_controller)


        self.entry_has_focus = False
        focus_controller = Gtk.EventControllerFocus.new()
        focus_controller.connect("enter", self.on_entry_focus_in)
        focus_controller.connect("leave", self.on_entry_focus_out)
        self.entry.add_controller(focus_controller)

        self.offset_x = 0
        self.offset_y = 0

        self.scale = 1.0
        self.hovered_cell = None
        self.selected = "A1"
        self.go_mode = False
        self.go_col = ""
        self.go_row = ""
        self.insert_bug = False

        self.map_multiplier = ""
        self.keymap = {
            "h": self.move_left,
            "j": self.move_down,
            "k": self.move_up,
            "l": self.move_right,
            "i": self.insert_mode,
            "g": self.set_go_mode,
        }

        self.da = Gtk.DrawingArea()
        self.da.set_draw_func(self.on_draw)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_child(self.da)

        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.VERTICAL, MIN_SCALE, MAX_SCALE, 0.01)
        self.slider.set_value(self.scale)
        self.slider.connect("value-changed", self.on_slider_changed)
        self.scroll.set_hexpand(True)  
        self.scroll.set_vexpand(True)

        self.slider.set_hexpand(False)
        self.slider.set_vexpand(True)

        self.append(self.entry)
        self.append(self.scroll)

        self.zoom_gesture = Gtk.GestureZoom.new()
        self.zoom_gesture.connect("scale-changed", self.on_pinch_zoom)
        self.da.add_controller(self.zoom_gesture)

        scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL | Gtk.EventControllerScrollFlags.HORIZONTAL)
        scroll_controller.connect("scroll", self.on_scroll)
        self.da.add_controller(scroll_controller)

        motion_controller = Gtk.EventControllerMotion.new()
        motion_controller.connect("motion", self.on_mouse_move)
        self.da.add_controller(motion_controller)

        click_controller = Gtk.GestureClick.new()
        click_controller.connect("pressed", self.on_mouse_click)
        self.da.add_controller(click_controller)


    def on_draw(self, area, ctx, width, height):
        ctx.save()
        ctx.translate(self.offset_x, self.offset_y)
        ctx.scale(self.scale, self.scale)

        ctx.select_font_face("CMU Serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(12)

        for c, column in enumerate(columns):
            for r, cell_id in enumerate(column):
                cell = cells[cell_id]

                x0 = c * CELL_W
                y0 = r * CELL_H
                x1 = x0 + CELL_W
                y1 = y0 + CELL_H

                if self.selected == cell_id:
                    ctx.set_source_rgb(0.2, 0.4, 1.0)
                    ctx.rectangle(x0, y0, CELL_W, CELL_H)
                    ctx.set_line_width(2)
                    ctx.stroke()
                elif self.hovered_cell == cell_id:
                    ctx.set_source_rgb(0.7,0.8,1.0)
                    ctx.rectangle(x0, y0, CELL_W, CELL_H)
                    ctx.set_line_width(2)
                    ctx.stroke()
                else:
                    ctx.set_source_rgb(0.5, 0.5, 0.5)
                    ctx.rectangle(x0, y0, CELL_W, CELL_H)
                    ctx.set_line_width(0.4)
                    ctx.stroke()

                formula = cell.formula
                if formula:
                    try:
                        cell.value = run(formula)
                    except Exception as e:
                        cell.value = str(e)
                
                text = str(cell.value)
                xbearing, ybearing, textw, texth, _, _ = ctx.text_extents(text)
                tx = x0 + (CELL_W - textw) / 2 - xbearing
                ty = y0 + (CELL_H - texth) / 2 - ybearing

                ctx.set_source_rgb(0, 0, 0)
                ctx.move_to(tx, ty)
                ctx.show_text(text)


        ctx.select_font_face("CMU Sans Serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(12/self.scale)

        bw = .4

        for c, cell_id in enumerate(rows[0]):
            x0 = c * CELL_W
            y0 = 0
            text = cells[cell_id].col_str

            if c == cells[self.selected].column:
                ctx.select_font_face("CMU Sans Serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                bw = 2

            xbearing, ybearing, textw, texth, _, _ = ctx.text_extents(text)
            tx = x0 + (CELL_W - textw) / 2 - xbearing 
            ty = y0 + (CELL_H/self.scale - texth) / 2 - ybearing - self.offset_y/self.scale
            ctx.set_source_rgb(0.75294118,0.75294118,0.75294118)
            ctx.rectangle(x0, y0-self.offset_y/self.scale, CELL_W, CELL_H/self.scale)
            ctx.fill()
            ctx.set_source_rgb(0, 0, 0)
            ctx.rectangle(x0, y0-self.offset_y/self.scale, CELL_W, CELL_H/self.scale)
            ctx.set_line_width(bw)
            ctx.stroke()
            ctx.move_to(tx,ty)
            ctx.show_text(text)
            if c == cells[self.selected].column:
                ctx.select_font_face("CMU Sans Serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_SLANT_NORMAL)
                bw = .4

        for r, cell_id in enumerate(columns[0]):
            x0 = 0
            y0 = r * CELL_H
            text = str(r+1)

            if r == cells[self.selected].row:
                ctx.select_font_face("CMU Sans Serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                bw = 2

            xbearing, ybearing, textw, texth, _, _ = ctx.text_extents(text)
            tx = x0 + (40/self.scale - textw) / 2 - xbearing - self.offset_x/self.scale
            ty = y0 + (CELL_H - texth) / 2 - ybearing
            ctx.set_source_rgb(0.75294118,0.75294118,0.75294118)
            ctx.rectangle(x0-self.offset_x/self.scale, y0, 40/self.scale, CELL_H)
            ctx.fill()
            ctx.set_source_rgb(0, 0, 0)
            ctx.rectangle(x0-self.offset_x/self.scale, y0, 40/self.scale, CELL_H)
            ctx.set_line_width(bw)
            ctx.stroke()
            ctx.move_to(tx,ty)
            ctx.show_text(text)
            if r == cells[self.selected].row:
                ctx.select_font_face("CMU Sans Serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_SLANT_NORMAL)
            bw = .4

        xbearing, ybearing, textw, texth, _, _ = ctx.text_extents(self.selected)
        tx = (40/self.scale - textw) / 2 - xbearing - self.offset_x/self.scale
        ty = (CELL_H/self.scale - texth) / 2 - ybearing - self.offset_y/self.scale
        ctx.set_source_rgb(0.75294118,0.75294118,0.75294118)
        ctx.rectangle(0-self.offset_x/self.scale, 0-self.offset_y/self.scale, 40/self.scale, CELL_H/self.scale)
        ctx.fill()
        ctx.set_source_rgb(0, 0, 0)
        ctx.rectangle(0-self.offset_x/self.scale, 0-self.offset_y/self.scale, 40/self.scale, CELL_H/self.scale)
        ctx.set_line_width(.4)
        ctx.stroke()
        ctx.move_to(tx,ty)
        ctx.show_text(self.selected)

        ctx.restore()

    def on_pinch_zoom(self, gesture, scale, _data=None):
        damping = 0.2

        event = gesture.get_last_event()
        if event is None:
            x, y = self.da.get_allocated_width() / 2, self.da.get_allocated_height() / 2
        else:
            pos = event.get_position()
            x, y = pos.x, pos.y

        content_x = (x - self.offset_x) / self.scale
        content_y = (y - self.offset_y) / self.scale

        new_scale = self.scale * (1 + (scale - 1) * damping)
        new_scale = max(MIN_SCALE, min(MAX_SCALE, new_scale))

        ox = x - content_x * new_scale
        oy = y - content_y * new_scale
        self.offset_x = ox if ox < 40 else 40
        self.offset_y = oy if oy < CELL_H else CELL_H

        self.scale = new_scale
        self.slider.set_value(self.scale)
        self.da.queue_draw()


    def on_scroll(self, controller, dx, dy):
        state = Gdk.ModifierType.CONTROL_MASK
        event_state = controller.get_current_event_state()
        if event_state & state:
            factor = 1.0 - dy * 0.01
            new_scale = max(MIN_SCALE, min(MAX_SCALE, self.scale * factor))
            self.scale = new_scale
            self.slider.set_value(self.scale)
            self.da.queue_draw()
            return True
        ox = self.offset_x - dx
        oy = self.offset_y - dy
        self.offset_x = ox if ox < 40 else 40
        self.offset_y = oy if oy < CELL_H else CELL_H
        self.da.queue_draw()
        return True


    def on_slider_changed(self, slider):
        self.scale = slider.get_value()
        self.da.queue_draw()


    def on_mouse_move(self, controller, x, y):
        x -= self.offset_x
        y -= self.offset_y
        cell_x = int(x / self.scale // CELL_W)
        cell_y = int(y / self.scale // CELL_H)
        if 0 <= cell_x < COLS and 0 <= cell_y < ROWS:
            self.hovered_cell = columns[cell_x][cell_y]
        else:
            self.hovered_cell = None
        self.da.queue_draw()

        
    def on_mouse_click(self, controller, e, x, y):
        x -= self.offset_x
        y -= self.offset_y
        cell_x = int(x / self.scale // CELL_W)
        cell_y = int(y / self.scale // CELL_H)
        if 0 <= cell_x < COLS and 0 <= cell_y < ROWS:
            cell = columns[cell_x][cell_y]
            if self.selected == cell:
                self.entry.set_text(cells[self.selected].formula)
                self.window.set_focus(self.entry)
            else:
                self.selected = cell
                self.entry.set_text(cells[self.selected].formula)
                self.window.set_focus(None)
        else:
            self.selected = ""
        self.da.queue_draw()

    
    def on_edit(self, entry):
        self.window.set_focus(None)
        if self.selected != "":
            text = entry.get_text()
            cells[self.selected].formula = text
            self.entry.set_text("")
            self.da.queue_draw()


    def on_input(self, *args):
        print(args)
        return True


    def on_key_released(self, controller, keyval, keycode, state):
        key = Gdk.keyval_name(keyval)
        if key == "Escape":
            self.window.set_focus(None)
            self.entry_has_focus = False
            self.go_mode = False
            self.go_col = ""
            self.go_row = ""
            self.entry.set_text("")

        if self.go_mode:
            col = cells[self.selected].column
            row = cells[self.selected].row
            # exit
            if not key.isdigit() and self.go_row != "":
                self.go_mode = False
                self.go_col = ""
                self.go_row = ""
            # go to row in column
            elif key.isdigit():
                self.go_row += key
                self.select(cells[self.selected].col_str+self.go_row)
            # go to column
            elif key.upper() in CHARS:
                self.go_col += key.upper()
                self.select(self.go_col+str(row+1))

        if not self.entry_has_focus and not self.go_mode:
            try:
                self.keymap[key]()
            except Exception as e:
                pass
            if key.isdigit():
                self.map_multiplier += key
            elif self.map_multiplier:
                self.map_multiplier = ""
            self.da.queue_draw()
            return True
        elif self.entry_has_focus:
            text = self.entry.get_text()
            if self.entry.get_selection_bounds() == ():
                if text and key != "BackSpace":
                    lsp = []
                    for glob in formula_globals:
                        if glob.startswith(text):
                            lsp.append(glob)
                    if len(lsp) > 0:
                        s = len(text)
                        self.entry.set_text(lsp[0])
                        self.entry.select_region(s, -1)

        self.da.queue_draw()
        return True
            
    def on_key_pressed(self, controller, keyval, keycode, state):
        return True

    def select(self, selection):
        self.selected = selection
        self.entry.set_text(cells[self.selected].formula)


    def on_entry_focus_in(self, event):
        self.entry_has_focus = True

    def on_entry_focus_out(self, event):
        self.entry_has_focus = False


    def move(self, x: int=0, y:int=0):
        x *= int(self.map_multiplier) if self.map_multiplier else 1
        y *= int(self.map_multiplier) if self.map_multiplier else 1
        cell = cells[self.selected]
        self.select(columns[cell.column+x][cell.row+y])

    def move_left(self): self.move(-1,0)
    def move_down(self): self.move(0,1)
    def move_up(self): self.move(0,-1) 
    def move_right(self): self.move(1,0)

    def set_go_mode(self): self.go_mode = True

    def insert_mode(self):
        self.entry.grab_focus()
        self.entry.set_text(cells[self.selected].formula)


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="net.studiodaw.egocell")

    def do_activate(self):
        win = Gtk.ApplicationWindow(application=self)
        win.set_default_size(900, 400)
        win.set_title("egocell")

        sheet = Sheet(win)

        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", sheet.on_key_pressed)
        key_controller.connect("key-released", sheet.on_key_released)
        win.add_controller(key_controller)
    
        win.set_child(sheet)
        win.present()

if __name__ == "__main__":
    app = App()
    app.run()
