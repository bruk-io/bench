"""Wire: a scene as it crosses to the browser - JSON, and the buffers beside it.

A :data:`bench.scene.Scene` is JSON-shaped so a browser can read it. This module is where it
becomes text, where a mesh's and an engraving's long lists are taken out into buffers that
cross without being written out digit by digit, and the one place that says which of a scene's
files are bytes written as base64 rather than text.
"""

import json
from array import array

from .scene import Scene

STL = ".stl"
"""One body, as the triangles a slicer reads - bytes, so base64."""

THREE_MF = ".3mf"
"""Every body of a run in one package, named - also bytes, and also base64."""

_BINARY = (STL, THREE_MF)
"""The file extensions a run writes as bytes rather than text."""


def binary(filename: str) -> bool:
    """Whether a scene's file of that name is bytes written as base64 rather than text.

    A scene is JSON, so ``files`` maps a name to a string either way; this is the one place
    that says which strings have to be decoded before they are written to disk. Today that
    is the STLs and the 3MF - everything a printer reads, and nothing a cutter does.
    """
    return filename.endswith(_BINARY)


def scene_json(scene: Scene) -> str:
    """``scene`` as the JSON text a browser parses."""
    return json.dumps(scene)


def scene_wire(scene: Scene) -> tuple[str, list[array[float] | array[int]]]:
    """``scene`` as the worker posts it to the page: the JSON, with every part's long lists
    taken out and replaced by the numbers of the buffers holding them, and the buffers.

    A mesh is thousands of numbers, and a number in JSON is text written out digit by digit on
    one side and parsed back on the other. As an :class:`array.array` it crosses into
    JavaScript as one copy of its bytes and on to the page as a transfer. A part's mesh takes
    the next two buffers - ``positions`` a float one, ``ref_index`` the unsigned one after it
    - and then its engraving marks the two after that, ``segments`` and ``ref_index``.

    A reference body, when there is one, takes the last two buffers of all, after every
    part's: it is one body rather than one per part, so it is counted once at the end rather
    than threaded through the loop.
    """
    if not scene["ok"]:
        return scene_json(scene), []
    buffers: list[array[float] | array[int]] = []
    parts: list[dict[str, object]] = []
    for part in scene["parts"]:
        wired: dict[str, object] = {**part}
        mesh = part["mesh"]
        if mesh is not None:
            buffers += (array("f", mesh["positions"]), array("I", mesh["ref_index"]))
            wired["mesh"] = {
                "positions": len(buffers) - 2,
                "ref_index": len(buffers) - 1,
                "refs": mesh["refs"],
            }
        marks = part["marks"]
        if marks is not None:
            buffers += (array("f", marks["segments"]), array("I", marks["ref_index"]))
            wired["marks"] = {
                "segments": len(buffers) - 2,
                "ref_index": len(buffers) - 1,
                "refs": marks["refs"],
            }
        parts.append(wired)
    wired_scene: dict[str, object] = {**scene, "parts": parts}
    reference = scene["reference"]
    if reference is not None:
        buffers += (array("f", reference["positions"]), array("I", reference["ref_index"]))
        wired_scene["reference"] = {
            "positions": len(buffers) - 2,
            "ref_index": len(buffers) - 1,
            "refs": reference["refs"],
        }
    return json.dumps(wired_scene), buffers
