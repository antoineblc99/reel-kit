"""sdr.py — every clip that enters a project is SDR, bt709, 8-bit.

Why: an HDR source (iPhone HLG, DJI D-Log/HLG, bt2020 or PQ tags) makes HyperFrames switch to its HDR render pipeline,
which composites DOM layers wrongly (a hidden caption stays at ~35 % opacity) and outputs HEVC. Measured on 22/09/2026.
The color tags survive a plain H.264 re-encode, so this tone-maps HDR transfers and stamps bt709 on everything.
"""
import subprocess

HDR_TRANSFERS = {"arib-std-b67", "smpte2084", "bt2020-10", "bt2020-12"}


def color_info(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=pix_fmt,color_space,color_transfer,color_primaries", "-of", "csv=p=0", str(path)]).decode().strip().split(",")
    return {"pix_fmt": out[0] if out else "", "space": out[1] if len(out) > 1 else "", "transfer": out[2] if len(out) > 2 else "", "primaries": out[3] if len(out) > 3 else ""}


def is_hdr(path):
    c = color_info(path)
    return c["transfer"] in HDR_TRANSFERS or c["primaries"] == "bt2020" or "10le" in c["pix_fmt"] and c["space"].startswith("bt2020")


def has_filter(name):
    try:
        return f" {name} " in subprocess.check_output(["ffmpeg", "-hide_banner", "-filters"], stderr=subprocess.DEVNULL).decode()
    except Exception:
        return False


def sdr_vf(path, extra=""):
    """The -vf chain: tone-map an HDR source to bt709, otherwise just convert; `extra` (e.g. scale=...) goes first.
    With zscale (ffmpeg built with libzimg): exact HLG/PQ tone-mapping. Without it: the colorspace filter, bt2020 → bt709
    with a gamma approximation of HLG, close enough for talking heads and screens."""
    parts = [extra] if extra else []
    if is_hdr(path):
        if has_filter("zscale"):
            parts.append("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv")
        else:
            parts.append("colorspace=iall=bt2020:itrc=bt2020-10:all=bt709:format=yuv420p")
    parts.append("format=yuv420p")
    return ",".join(parts)


SDR_TAGS = ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv"]
