import wx
import pcbnew
import os
import logging
import sys
import math
import numpy as np

#TODO(HEIDT) get the userspace units and use those instead of mm for outward facing things

if __name__ == "__main__":
    import grid_track_GUI
else:
    from . import grid_track_GUI

# get version information
version_filename = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "version.txt"
)
with open(version_filename) as f:
    VERSION = f.readline().strip()
# > V5.1.5 and V 5.99 build information
if hasattr(pcbnew, "GetBuildVersion"):
    BUILD_VERSION = pcbnew.GetBuildVersion()
else:
    BUILD_VERSION = "Unknown"


class GridTrackDialog(grid_track_GUI.CreateTrackDialog):
    # hack for new wxFormBuilder generating code incompatible with old wxPython
    # noinspection PyMethodOverriding
    def SetSizeHints(self, sz1, sz2):
        try:
            # wxPython 3
            self.SetSizeHintsSz(sz1, sz2)
        except TypeError:
            # wxPython 4
            super(GridTrackDialog, self).SetSizeHints(sz1, sz2)

    def __init__(self, parent):
        grid_track_GUI.CreateTrackDialog.__init__(self, parent)


def find_pcbnew_w():
    windows = wx.GetTopLevelWindows()
    pcbneww = [w for w in windows if "pcbnew" in w.GetTitle().lower()]
    if len(pcbneww) != 1:
        return None
    return pcbneww[0]


def create_arc(
    board: pcbnew.BOARD,
    center: np.ndarray,
    start_point: np.ndarray,
    end_point: np.ndarray,
    width: float,
):
    new_arc = pcbnew.PCB_ARC(board)
    fromMM = lambda x: pcbnew.FromMM(float(x))
    R = np.linalg.norm(start_point - center)

    AB = end_point - start_point
    mid = AB / 2.0
    mid_chord = start_point + mid
    mid_circle = (mid_chord / np.linalg.norm(mid_chord)) * R
    midpoint = -mid_circle

    p2 = pcbnew.wxPoint(fromMM(start_point[0]), fromMM(start_point[1]))
    p1 = pcbnew.wxPoint(fromMM(end_point[0]), fromMM(end_point[1]))
    md = pcbnew.wxPoint(fromMM(midpoint[0]), fromMM(midpoint[1]))

    new_arc.SetStart(p1)
    new_arc.SetMid(md)
    new_arc.SetEnd(p2)
    new_arc.SetWidth(fromMM(width))
    new_arc.SetLayer(pcbnew.F_Cu)
    length = np.abs((new_arc.GetAngle() / 10.0) * (np.pi / 180.0) * R)
    board.Add(new_arc)
    return length, new_arc


def create_track(board: pcbnew.BOARD, start: np.ndarray, end: np.ndarray, width: float):
    new_track = pcbnew.PCB_TRACK(board)
    fromMM = lambda x: pcbnew.FromMM(float(x))

    new_track.SetStart(pcbnew.wxPoint(fromMM(start[0]), fromMM(start[1])))
    new_track.SetEnd(pcbnew.wxPoint(fromMM(end[0]), fromMM(end[1])))
    new_track.SetWidth(fromMM(width))
    new_track.SetLayer(pcbnew.F_Cu)
    board.Add(new_track)
    return np.linalg.norm(start - end), new_track


def get_y_from_circle(x: float, radius: float):
    return np.sqrt(radius**2.0 - x**2.0)

def extend_group(tracks: list, group: pcbnew.PCB_GROUP):
    #TODO(HEIDT) both this and calc length are using implicit linking to track list
    for track in tracks:
        group.AddItem(track[1])

def calc_length(tracks: list, length: float) -> float: 
    # TODO(HEIDT) this doens't account for the extra length from the radius
    for track in tracks:
        length += track[0]
    return length

def make_round_array(
    board: pcbnew.BOARD, center: np.ndarray, width: float, radius: float, spacing: float
):
    gap = spacing + width
    start_y = get_y_from_circle(-gap, radius)
    group = pcbnew.PCB_GROUP(board)
    board.Add(group)
    length = 0.0

    while start_y > spacing * 2 + width * 2:
        start_point = np.array((-gap, start_y))
        end_point = np.array((gap, start_y))

        next_start = np.array(end_point)
        next_start[1] -= width + spacing
        next_end = np.array(start_point)
        next_end[1] -= width + spacing

        # TODO(HEIDT) repeated start_y reduction here and in next_start/end
        start_y -= 2 * (width + spacing)
        finishing_point = np.array(next_end)
        finishing_point[1] = start_y

        a1 = create_arc(board, center, start_point, end_point, width)
        t1 = create_track(board, end_point, next_start, width)
        a2 = create_arc(board, center, next_start, next_end, width)
        t2 = create_track(board, next_end, finishing_point, width)
        extend_group((a1, t1, a2, t2), group)
        length = calc_length((a1, t1, a2, t2), length)

    wx.LogMessage(f"Total length is approx {length} mm")


class CreateGridTrack(pcbnew.ActionPlugin):
    """
    A script to make grid tracks
    """

    def defaults(self):
        self.name = "Make Grid Tracks"
        self.category = "Modify Drawing PCB"
        self.description = "Creates a round or rectangular grid track"
        self.show_toolbar_button = True

    def Run(self):
        dlg = GridTrackDialog(find_pcbnew_w())
        res = dlg.ShowModal()  # if user clicked OK
        board = pcbnew.GetBoard()
        print("test")
        # if user clicked OK
        if res == wx.ID_OK:
            # wx.LogMessage("Clicked ok!")
            tracksize = float(dlg.m_tracksize.GetLineText(0))
            trackspacing = float(dlg.m_trackspacing.GetLineText(0))
            diameter = float(dlg.m_diameter.GetLineText(0))
            # crete_circle(board, tracksize, trackspacing, diameter)
            # create_arc(board, np.array((0, 0)), np.array((20, 20)), np.array((10, 20)))
            # create_track(board, np.array((0, 0)), np.array((30, 0)), 5.0)
            make_round_array(
                board, np.array([0, 0]), tracksize, diameter / 2.0, trackspacing
            )
        # if dlg.chkbox_tracks.GetValue():

        pcbnew.Refresh()
