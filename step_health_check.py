# -*- coding: utf-8 -*-
"""
STEP 体检：导入 SolidWorks 之前先看一眼这个文件有没有毛病。
用法：把 .step/.stp 文件拖到 STEP体检.bat 上，或
      python step_health_check.py "D:\\xxx\\model.STEP"
不修改原文件，只读。
"""
import re
import sys
import os

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    if len(sys.argv) < 2:
        print("用法: 把 STEP 文件拖到 STEP体检.bat 上")
        return 2
    path = sys.argv[1]
    if not os.path.isfile(path):
        print("[错误] 找不到文件: %s" % path)
        return 2

    size = os.path.getsize(path)
    print("=" * 62)
    print("文件: %s" % os.path.basename(path))
    print("大小: %.1f MB" % (size / 1048576.0))
    print("=" * 62)

    data = open(path, "rb").read()

    head = data[:4000].decode("latin-1")
    m = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", head)
    schema = m.group(1) if m else "?"
    fname = "?"
    m = re.search(rb"FILE_NAME\s*\(\s*'([^']*)'", data[:4000])
    if m:
        raw = m.group(1)
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                fname = raw.decode(enc)
                break
            except Exception:
                continue
    print("格式: STEP %s   内部文件名: %s" % (schema, fname))

    # 单位
    milli = b"SI_UNIT ( .MILLI., .METRE. )" in data or b"SI_UNIT(.MILLI.,.METRE.)" in data
    metre = (b"SI_UNIT ( $, .METRE. )" in data) or (b"SI_UNIT($,.METRE.)" in data)
    unit = "毫米 (mm)" if milli else ("米 (m)" if metre else "未知")
    scale = 1.0 if milli else 1000.0     # 1 文件单位 = ? mm
    print("长度单位: %s" % unit)
    print("")

    def count(tag):
        return data.count(tag)

    n_product = count(b"PRODUCT (") or count(b"PRODUCT(")
    print("内容统计：")
    print("  产品(零件/子装配)  %d" % n_product)
    print("  实体(BREP)        %d" % (count(b"MANIFOLD_SOLID_BREP") + count(b"FACETED_BREP")))
    print("  曲面模型          %d" % (count(b"SHELL_BASED_SURFACE_MODEL") + count(b"OPEN_SHELL")))
    print("  面(ADVANCED_FACE) %d" % count(b"ADVANCED_FACE"))
    print("  点(CARTESIAN)     %d" % count(b"CARTESIAN_POINT"))
    print("")

    pp = re.compile(rb"#\d+\s*=\s*CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*"
                    rb"([-+0-9.Ee]+)\s*,\s*([-+0-9.Ee]+)\s*,\s*([-+0-9.Ee]+)\s*\)\s*\)")
    pts = []
    for mm_ in pp.finditer(data):
        pts.append(tuple(float(mm_.group(i)) * scale for i in (1, 2, 3)))

    n = len(pts)
    if not n:
        print("[警告] 一个坐标点都没读到，文件可能不完整。")
        return 1

    mags = sorted(max(abs(c) for c in p) for p in pts)
    p50 = mags[len(mags) // 2]
    p99 = mags[min(len(mags) - 1, int(len(mags) * 0.99))]
    limit = max(20.0 * p99, 1000.0)          # 远超主体尺寸才算离群
    far_pts = [p for p in pts if max(abs(c) for c in p) > limit]
    keep = [p for p in pts if max(abs(c) for c in p) <= limit]
    if not keep:
        keep = pts
        far_pts = []

    def bbox(ps):
        lo = [min(p[i] for p in ps) for i in range(3)]
        hi = [max(p[i] for p in ps) for i in range(3)]
        return lo, hi

    lo, hi = bbox(pts)
    klo, khi = bbox(keep)
    ext = [round(hi[i] - lo[i], 1) for i in range(3)]
    kext = [round(khi[i] - klo[i], 1) for i in range(3)]

    print("全部几何包围盒 (mm): %s ~ %s" % ([round(v, 1) for v in lo], [round(v, 1) for v in hi]))
    print("  整体尺寸: %s mm（约 %.2f m）" % (ext, max(ext) / 1000.0))
    print("  去掉离群点后: %s mm" % kext)
    print("  离群点(超过 %.0f mm): %d / %d    典型尺寸(中位) %.0f mm" % (limit, len(far_pts), n, p50))
    print("")

    print("=" * 62)
    if far_pts:
        big = max(max(abs(c) for c in p) for p in far_pts) / 1000.0
        print("[警告] 有 %d 个点跑到 %.1f 米开外（正常主体只有 %s mm）。" % (len(far_pts), big, kext))
        print("       说明有零件被导成了无界/巨大的面，导入后极可能白屏：")
        print("       缩放至适合时视野被撑到几公里，整车只剩不到 1 个像素。")
        print("")
        print("       对策：导入后双击 修复白屏.bat；或者让发文件的人重导那个零件。")
    else:
        print("[正常] 没发现离群点，几何范围 %s mm，是干净的 STEP。" % ext)
        if max(ext) > 5000:
            print("       注意：这个零件本身就挺大（%.1f m），如果导入后尺寸不对，" % (max(ext) / 1000.0))
            print("       检查导入单位是不是选错了。")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
