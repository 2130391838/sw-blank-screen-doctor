# -*- coding: utf-8 -*-
"""
SolidWorks 白屏急救 —— 一键：找出超大垃圾面零件 -> 压缩 -> 缩放至适合

用法（平时双击 bat 就行，不用手打）：
    python step_blank_doctor.py --fix     一键修复（压缩问题零件 + 缩放到合适）
    python step_blank_doctor.py --dry     只诊断，不动模型
    python step_blank_doctor.py --undo    还原上一次修复（解除压缩）

安全性：不关闭文档、不保存文件、不删除特征。压缩可用 --undo、
       Ctrl+Z 或右键"解除压缩"还原。

判定逻辑（三层，防止误伤正常的大零件）：
    1) 组件包围盒 > max(3 米, 10×P90, 30×P50) 才算候选；
    2) 全体包围盒 / 去掉候选后的包围盒 > 50 倍，才确认"视野被撑大"；
    3) 两条都满足才动手压缩。
"""
import os
import sys
import json
import time
import statistics

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import win32com.client as win32
except ImportError:
    print("[错误] 缺少 pywin32：pip install pywin32")
    sys.exit(2)

MODE = "fix"
if "--dry" in sys.argv or "--report" in sys.argv:
    MODE = "dry"
if "--undo" in sys.argv:
    MODE = "undo"

MIN_ABS = 3.0        # 候选最小尺寸（米）
P90_FACTOR = 10.0    # 也要大于普通组件的 10 倍
P50_FACTOR = 30.0    # 以及中位组件的 30 倍
RATIO_TOTAL = 8.0    # 撑大倍数确认阈值

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "undo-log.json")


def prop(obj, name, default=None):
    """SW 的属性在不同版本/接口下可能变成方法，兼容。"""
    try:
        v = getattr(obj, name)
    except Exception:
        return default
    if callable(v):
        try:
            return v()
        except Exception:
            return default
    return v


def comp_box(c):
    """组件包围盒，装配坐标，单位米；失败返回 None。"""
    try:
        b = list(c.GetBox(True, False))
    except Exception:
        return None
    return b if len(b) >= 6 else None


def is_leaf(c):
    """只处理零件级组件；子装配体的包围盒会连带子件，不能当异常件。"""
    path = prop(c, "GetPathName", "") or ""
    if isinstance(path, str) and path:
        return not path.lower().endswith(".sldasm")
    ch = prop(c, "GetChildren", None)
    try:
        return not ch
    except Exception:
        return True


def union(boxes):
    if not boxes:
        return None
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
            max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes)]


def size(b):
    return max(b[3] - b[0], b[4] - b[1], b[5] - b[2]) if b else 0.0


def save_log(entry):
    try:
        data = []
        if os.path.isfile(LOG):
            try:
                data = json.load(open(LOG, "r", encoding="utf-8"))
            except Exception:
                data = []
        data.append(entry)
        json.dump(data[-20:], open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass


def undo():
    if not os.path.isfile(LOG):
        print("[提示] 没有修复记录，不需要还原。")
        return 0
    try:
        data = json.load(open(LOG, "r", encoding="utf-8"))
    except Exception:
        print("[提示] 记录读不出来，直接右键 > 解除压缩 也行。")
        return 1
    if not data:
        print("[提示] 记录是空的。")
        return 0
    entry = data[-1]

    sw = win32.GetActiveObject("SldWorks.Application")
    doc = None
    for d in sw.GetDocuments or []:
        if d.GetTitle == entry.get("doc"):
            doc = d
            break
    if doc is None:
        print("[提示] 那个装配体已经关了，不用还原。")
        return 0
    try:
        sw.ActivateDoc(doc.GetTitle)
    except Exception:
        pass

    by_name = {c.Name2: c for c in (doc.GetComponents(False) or [])}
    ok = 0
    for name in entry.get("comps", []):
        c = by_name.get(name)
        if c is None:
            continue
        try:
            c.Visible = True
            ok += 1
        except Exception:
            pass
    try:
        doc.ViewZoomtofit2()
    except Exception:
        pass
    print("已还原 %d 个零件（重新显示）。" % ok)
    print("如果还是白屏，说明原因不是垃圾面，双击 只诊断.bat 看结论。")
    return 0


def main():
    try:
        sw = win32.GetActiveObject("SldWorks.Application")
    except Exception:
        print("[错误] 没找到正在运行的 SolidWorks。先打开 SolidWorks 和白屏的文件。")
        return 2

    if MODE == "undo":
        return undo()

    doc = sw.ActiveDoc
    if doc is None:
        print("[提示] SolidWorks 里没有打开的文档。")
        return 1

    # 找目标装配体：当前窗口优先，否则找组件最多的装配体
    asm = doc if prop(doc, "GetType") == 2 else None
    if asm is None:
        cands = [d for d in (sw.GetDocuments or []) if prop(d, "GetType") == 2]
        cands.sort(key=lambda d: len(d.GetComponents(False) or []), reverse=True)
        if cands:
            asm = cands[0]
            try:
                sw.ActivateDoc(asm.GetTitle)
            except Exception:
                pass

    if asm is None:
        print("当前文档：%s（零件）" % doc.GetTitle)
        print("[提示] 白屏的是装配体的话，先 Ctrl+Tab 切到装配体窗口再运行。")
        print("       如果白屏的就是这个零件，打开它看看有没有超大的曲面实体，删掉即可。")
        return 1

    print("装配体：%s" % asm.GetTitle)
    comps = asm.GetComponents(False) or []
    if not comps:
        print("[提示] 这个装配体里没有组件。")
        return 1

    rows = []
    for c in comps:
        if not is_leaf(c):
            continue
        b = comp_box(c)
        if b is not None:
            rows.append((c, b, size(b)))
    if not rows:
        print("[提示] 读不到零件包围盒（可能还在导入，或全是子装配体）。")
        return 1

    sizes = sorted(r[2] for r in rows)
    p50 = sizes[len(sizes) // 2]
    p90 = sizes[min(len(sizes) - 1, int(len(sizes) * 0.9))]
    thr = max(MIN_ABS, P90_FACTOR * p90, P50_FACTOR * p50)

    cands = [r for r in rows if r[2] > thr]
    rest = [r for r in rows if r[2] <= thr]

    if not cands:
        print("没有发现超大垃圾面（阈值 %.1f m，最大组件 %.2f m）。" % (thr, sizes[-1]))
        print("空白多半是别的原因：")
        print("  1) 先按 F（缩放至适合）")
        print("  2) 选中任意零件 -> 右键 -> 缩放至选择")
        print("  3) 视图 > 显示 > 带边线上色")
        print("  4) 视图 > 关闭剖面视图")
        try:
            asm.ViewZoomtofit2()
        except Exception:
            pass
        return 0

    total_ext = size(union([r[1] for r in rows]))
    rest_ext = size(union([r[1] for r in rest])) if rest else 0.0

    print("候选异常组件 %d 个（阈值 %.1f m）：" % (len(cands), thr))
    for c, b, e in sorted(cands, key=lambda x: -x[2])[:6]:
        print("   %-58s 约 %.0f m" % (c.Name2[-58:], e))

    if rest_ext and total_ext / rest_ext < RATIO_TOTAL:
        print("")
        print("[结论] 整体尺寸只有正常部分的 %.0f 倍，模型本身就该这么大，" % (total_ext / rest_ext))
        print("       不算垃圾面，不做改动。试试按 F 或用 视图 > 缩放至选择。")
        return 0

    print("")
    print("整体范围 %.0f m，正常部分只有 %.2f m —— 视野被撑大了 %d 倍，确认是这个问题。"
          % (total_ext, rest_ext, int(total_ext / rest_ext) if rest_ext else 0))

    if MODE == "dry":
        print("（诊断模式，没有改动模型。要修复请双击 修复白屏.bat）")
        return 0

    done, failed = [], []
    for c, b, e in cands:
        try:
            c.Visible = False
            done.append(c.Name2)
        except Exception:
            failed.append(c.Name2)

    try:
        asm.ViewZoomtofit2()
    except Exception:
        pass

    print("")
    print("已把这些零件藏起来（%d 个），视图也缩放到合适了 —— 现在应该能看到模型。" % len(done))
    if failed:
        print("（%d 个没藏上，手动右键 > 隐藏 即可）" % len(failed))
    if done:
        save_log({"doc": asm.GetTitle, "time": time.strftime("%Y-%m-%d %H:%M:%S"), "comps": done})
        print("想彻底不让它们参与计算：在树里右键那几个零件 > 压缩（可选，不改也能看）。")
        print("反悔的话：双击 撤销修复.bat。")
    if not prop(asm, "GetPathName"):
        print("提醒：这是没保存的导入结果，关掉 SolidWorks 就没了 —— 先 文件 > 打包(Pack and Go)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
