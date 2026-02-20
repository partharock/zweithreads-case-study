#!/usr/bin/env python3
"""Generate a comprehensive AAOS contacts-cache case-study PPTX without external deps."""

from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SLIDE_WIDTH = 12192000
SLIDE_HEIGHT = 6858000

TOKEN_RE = re.compile(
    r'//.*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|@[A-Za-z_]\w*|\b[A-Za-z_]\w*\b|\d+(?:_\d+)*|\s+|.'
)
NUMBER_TOKEN_RE = re.compile(r"^\d+(?:_\d+)*$")
IDENTIFIER_TOKEN_RE = re.compile(r"^[A-Za-z_]\w*$")
JAVA_KEYWORDS = {
    "if",
    "else",
    "for",
    "while",
    "switch",
    "case",
    "default",
    "return",
    "try",
    "catch",
    "finally",
    "throw",
    "throws",
    "new",
    "class",
    "interface",
    "enum",
    "extends",
    "implements",
    "public",
    "private",
    "protected",
    "static",
    "final",
    "void",
    "int",
    "long",
    "float",
    "double",
    "boolean",
    "char",
    "byte",
    "short",
    "this",
    "super",
    "import",
    "package",
    "override",
    "assert",
}
JAVA_LITERALS = {"true", "false", "null"}


@dataclass(frozen=True)
class SlideData:
    title: str
    bullets: list[str]
    code_title: str | None = None
    code: str | None = None
    footer: str | None = None
    image_key: str | None = None
    image_caption: str | None = None
    table: "TableData | None" = None
    index_entries: list["IndexEntry"] | None = None


@dataclass(frozen=True)
class IndexEntry:
    label: str
    subtitle: str
    target_title: str


@dataclass(frozen=True)
class TableData:
    headers: list[str]
    rows: list[list[str]]
    col_widths: list[int] | None = None


@dataclass(frozen=True)
class RunData:
    text: str
    color: str
    bold: bool = False
    italic: bool = False
    hyperlink_rid: str | None = None


def run_xml(
    text: str,
    font: str,
    size: int,
    color: str,
    bold: bool = False,
    italic: bool = False,
    preserve: bool = False,
    hyperlink_rid: str | None = None,
) -> str:
    attrs = [f'lang="en-US"', f'sz="{size}"']
    if bold:
        attrs.append('b="1"')
    if italic:
        attrs.append('i="1"')
    if hyperlink_rid:
        attrs.append('u="sng"')
    hyperlink_xml = (
        f'<a:hlinkClick r:id="{hyperlink_rid}" action="ppaction://hlinksldjump"/>'
        if hyperlink_rid
        else ""
    )
    text_attrs = ' xml:space="preserve"' if preserve else ""
    return (
        f"<a:r><a:rPr {' '.join(attrs)}><a:solidFill><a:srgbClr val=\"{color}\"/>"
        f"</a:solidFill><a:latin typeface=\"{font}\"/>{hyperlink_xml}</a:rPr>"
        f"<a:t{text_attrs}>{escape(text)}</a:t></a:r>"
    )


def paragraph_xml(
    text: str,
    font: str,
    size: int,
    color: str,
    bold: bool = False,
    italic: bool = False,
    preserve: bool = False,
    align: str | None = None,
    line_spacing_pct: int = 112000,
    space_before_pts: int = 0,
    space_after_pts: int = 120,
) -> str:
    ppr = paragraph_props_xml(
        align=align,
        line_spacing_pct=line_spacing_pct,
        space_before_pts=space_before_pts,
        space_after_pts=space_after_pts,
    )
    if text == "":
        return f"<a:p>{ppr}<a:endParaRPr lang=\"en-US\" sz=\"{size}\"/></a:p>"
    run = run_xml(text, font, size, color, bold=bold, italic=italic, preserve=preserve)
    return f"<a:p>{ppr}{run}<a:endParaRPr lang=\"en-US\" sz=\"{size}\"/></a:p>"


def paragraph_props_xml(
    align: str | None,
    line_spacing_pct: int,
    space_before_pts: int,
    space_after_pts: int,
) -> str:
    attrs = []
    if align:
        attrs.append(f'algn="{align}"')
    attr_str = f" {' '.join(attrs)}" if attrs else ""
    return (
        f"<a:pPr{attr_str}>"
        f"<a:lnSpc><a:spcPct val=\"{line_spacing_pct}\"/></a:lnSpc>"
        f"<a:spcBef><a:spcPts val=\"{space_before_pts}\"/></a:spcBef>"
        f"<a:spcAft><a:spcPts val=\"{space_after_pts}\"/></a:spcAft>"
        f"</a:pPr>"
    )


def paragraph_runs_xml(
    runs: Iterable[RunData],
    font: str,
    size: int,
    preserve: bool = False,
    align: str | None = None,
    line_spacing_pct: int = 108000,
    space_before_pts: int = 0,
    space_after_pts: int = 90,
) -> str:
    ppr = paragraph_props_xml(
        align=align,
        line_spacing_pct=line_spacing_pct,
        space_before_pts=space_before_pts,
        space_after_pts=space_after_pts,
    )
    run_xml_parts = [
        run_xml(
            run.text,
            font,
            size,
            run.color,
            bold=run.bold,
            italic=run.italic,
            preserve=preserve,
            hyperlink_rid=run.hyperlink_rid,
        )
        for run in runs
        if run.text
    ]
    if not run_xml_parts:
        return f"<a:p>{ppr}<a:endParaRPr lang=\"en-US\" sz=\"{size}\"/></a:p>"
    return f"<a:p>{ppr}{''.join(run_xml_parts)}<a:endParaRPr lang=\"en-US\" sz=\"{size}\"/></a:p>"


def shape_xml(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    paragraphs: Iterable[str],
    fill_color: str | None = None,
    line_color: str | None = None,
    line_width: int = 12700,
    body_pr_extra: str = "",
    click_hyperlink_rid: str | None = None,
) -> str:
    if fill_color:
        fill_xml = f"<a:solidFill><a:srgbClr val=\"{fill_color}\"/></a:solidFill>"
    else:
        fill_xml = "<a:noFill/>"

    if line_color:
        line_xml = f"<a:ln w=\"{line_width}\"><a:solidFill><a:srgbClr val=\"{line_color}\"/></a:solidFill></a:ln>"
    else:
        line_xml = "<a:ln><a:noFill/></a:ln>"

    paras_xml = "".join(paragraphs)
    nvpr_xml = (
        f'<p:nvPr><a:hlinkClick r:id="{click_hyperlink_rid}" action="ppaction://hlinksldjump"/></p:nvPr>'
        if click_hyperlink_rid
        else "<p:nvPr/>"
    )

    return f"""
<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="{escape(name)}"/>
    <p:cNvSpPr/>
    {nvpr_xml}
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    {fill_xml}
    {line_xml}
  </p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square" lIns="91440" tIns="45720" rIns="91440" bIns="45720" {body_pr_extra}/>
    <a:lstStyle/>
    {paras_xml}
  </p:txBody>
</p:sp>
""".strip()


def picture_xml(shape_id: int, name: str, x: int, y: int, cx: int, cy: int, rel_id: str) -> str:
    return f"""
<p:pic>
  <p:nvPicPr>
    <p:cNvPr id="{shape_id}" name="{escape(name)}"/>
    <p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>
    <p:nvPr/>
  </p:nvPicPr>
  <p:blipFill>
    <a:blip r:embed="{rel_id}"/>
    <a:stretch><a:fillRect/></a:stretch>
  </p:blipFill>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    <a:ln w="19050"><a:solidFill><a:srgbClr val="C7D2FE"/></a:solidFill></a:ln>
  </p:spPr>
</p:pic>
""".strip()


def table_cell_xml(
    text: str,
    fill_color: str,
    text_color: str,
    bold: bool = False,
    align: str = "l",
    size: int = 1125,
) -> str:
    paragraph = paragraph_xml(
        text,
        "Aptos",
        size,
        text_color,
        bold=bold,
        align=align,
        line_spacing_pct=108000,
        space_after_pts=30,
    )
    border = '<a:solidFill><a:srgbClr val="CBD5E1"/></a:solidFill>'
    return f"""
<a:tc>
  <a:txBody>
    <a:bodyPr wrap="square"/>
    <a:lstStyle/>
    {paragraph}
  </a:txBody>
  <a:tcPr marL="45720" marR="45720" marT="22860" marB="22860">
    <a:solidFill><a:srgbClr val="{fill_color}"/></a:solidFill>
    <a:lnL w="9525">{border}</a:lnL>
    <a:lnR w="9525">{border}</a:lnR>
    <a:lnT w="9525">{border}</a:lnT>
    <a:lnB w="9525">{border}</a:lnB>
  </a:tcPr>
</a:tc>
""".strip()


def table_xml(shape_id: int, x: int, y: int, cx: int, cy: int, table: TableData) -> str:
    col_count = len(table.headers)
    if col_count == 0:
        raise ValueError("Table must have at least one header column.")

    if table.col_widths and len(table.col_widths) == col_count:
        columns = table.col_widths
    else:
        per = cx // col_count
        columns = [per] * col_count
        columns[-1] += cx - (per * col_count)

    grid_cols = "".join(f'<a:gridCol w="{w}"/>' for w in columns)
    row_count = len(table.rows) + 1
    row_height = max(295000, cy // max(1, row_count))

    header_cells = []
    for idx, cell in enumerate(table.headers):
        align = "l" if idx == 0 else "ctr"
        header_cells.append(table_cell_xml(cell, "DBEAFE", "0F172A", bold=True, align=align, size=1100))
    rows_xml = [f'<a:tr h="{row_height}">{"".join(header_cells)}</a:tr>']

    for row_idx, raw_row in enumerate(table.rows):
        row = raw_row[:col_count] + ([""] * max(0, col_count - len(raw_row)))
        data_fill = "FFFFFF" if row_idx % 2 == 0 else "F8FAFC"
        row_cells = []
        for col_idx, cell in enumerate(row):
            cell_fill = "F8FAFC" if col_idx == 0 else data_fill
            row_cells.append(
                table_cell_xml(
                    cell,
                    cell_fill,
                    "0F172A" if col_idx == 0 else "1E293B",
                    bold=(col_idx == 0),
                    align="l",
                    size=1060,
                )
            )
        rows_xml.append(f'<a:tr h="{row_height}">{"".join(row_cells)}</a:tr>')

    return f"""
<p:graphicFrame>
  <p:nvGraphicFramePr>
    <p:cNvPr id="{shape_id}" name="Data Table"/>
    <p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr>
    <p:nvPr/>
  </p:nvGraphicFramePr>
  <p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></p:xfrm>
  <a:graphic>
    <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">
      <a:tbl>
        <a:tblPr firstRow="1" bandRow="1">
          <a:tableStyleId>{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}</a:tableStyleId>
        </a:tblPr>
        <a:tblGrid>{grid_cols}</a:tblGrid>
        {''.join(rows_xml)}
      </a:tbl>
    </a:graphicData>
  </a:graphic>
</p:graphicFrame>
""".strip()


def index_card_shape_xml(
    shape_id: int,
    x: int,
    y: int,
    cx: int,
    cy: int,
    title: str,
    subtitle: str,
    hyperlink_rid: str,
) -> str:
    paragraphs = [
        paragraph_runs_xml(
            [RunData(title, "1D4ED8", bold=True, hyperlink_rid=hyperlink_rid)],
            "Aptos",
            1500,
            line_spacing_pct=106000,
            space_after_pts=80,
        ),
        paragraph_xml(subtitle, "Aptos", 1175, "334155", line_spacing_pct=110000, space_after_pts=40),
        paragraph_runs_xml(
            [RunData("Click to open section", "2563EB", hyperlink_rid=hyperlink_rid)],
            "Aptos",
            1050,
            line_spacing_pct=104000,
            space_after_pts=0,
        ),
    ]
    return shape_xml(
        shape_id=shape_id,
        name=f"Index Card {title}",
        x=x,
        y=y,
        cx=cx,
        cy=cy,
        paragraphs=paragraphs,
        fill_color="F8FAFC",
        line_color="BFDBFE",
        line_width=19050,
        click_hyperlink_rid=hyperlink_rid,
    )


def format_body_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    if stripped.startswith(("-", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.")):
        return stripped
    return f"• {stripped}"


def highlight_code_line(line: str) -> list[RunData]:
    tokens = TOKEN_RE.findall(line)
    if not tokens:
        return []

    runs: list[RunData] = []
    for idx, token in enumerate(tokens):
        color = "E2E8F0"
        bold = False
        italic = False

        if token.startswith("//"):
            runs.append(RunData(token, "94A3B8", italic=True))
            break
        if token[:1] in {'"', "'"} and len(token) >= 2:
            color = "86EFAC"
        elif token.startswith("@"):
            color = "F0ABFC"
            bold = True
        elif NUMBER_TOKEN_RE.match(token):
            color = "FDBA74"
        elif token in JAVA_LITERALS:
            color = "FCA5A5"
            bold = True
        elif token in JAVA_KEYWORDS:
            color = "93C5FD"
            bold = True
        elif IDENTIFIER_TOKEN_RE.match(token):
            look_ahead = idx + 1
            while look_ahead < len(tokens) and tokens[look_ahead].isspace():
                look_ahead += 1
            if look_ahead < len(tokens) and tokens[look_ahead] == "(" and token not in JAVA_KEYWORDS:
                color = "C4B5FD"
            elif token[0].isupper():
                color = "67E8F9"
        elif token.isspace():
            color = "E2E8F0"
        runs.append(RunData(token, color, bold=bold, italic=italic))
    return runs


def slide_xml(
    slide: SlideData,
    slide_index: int,
    slide_count: int,
    index_link_rids: list[str] | None = None,
) -> str:
    shapes: list[str] = []

    next_shape_id = 2
    shapes.append(
        shape_xml(
            shape_id=next_shape_id,
            name="Top Accent",
            x=0,
            y=0,
            cx=SLIDE_WIDTH,
            cy=137160,
            paragraphs=[paragraph_xml("", "Aptos", 1000, "000000")],
            fill_color="2563EB",
            line_color=None,
        )
    )
    next_shape_id += 1

    shapes.append(
        shape_xml(
            shape_id=next_shape_id,
            name="Title",
            x=457200,
            y=190500,
            cx=11277600,
            cy=685800,
            paragraphs=[
                paragraph_xml(
                    slide.title,
                    "Aptos Display",
                    3400,
                    "0F172A",
                    bold=True,
                    line_spacing_pct=102000,
                    space_after_pts=180,
                )
            ],
        )
    )
    next_shape_id += 1

    has_table = slide.table is not None
    has_index = bool(slide.index_entries)
    image_only_layout = slide.image_key is not None and slide.code is None and not has_table and not has_index
    if slide.code is not None:
        body_height = 2300000
    elif has_index:
        body_height = 1066800
    elif has_table:
        body_height = 1371600
    else:
        body_height = 5003800
    body_x = 457200
    body_y = 914400
    body_width = 7073900 if image_only_layout else 11277600
    if image_only_layout:
        body_size = 1725
    elif has_index:
        body_size = 1650
    elif has_table:
        body_size = 1700
    else:
        body_size = 1825

    body_paragraphs = [
        paragraph_xml(
            format_body_line(line),
            "Aptos",
            body_size,
            "1E293B",
            line_spacing_pct=118000,
            space_after_pts=90,
        )
        for line in slide.bullets
    ]
    shapes.append(
        shape_xml(
            shape_id=next_shape_id,
            name="Body",
            x=body_x,
            y=body_y,
            cx=body_width,
            cy=body_height,
            paragraphs=body_paragraphs,
            fill_color="FFFFFF",
            line_color="DBE6FB",
            line_width=19050,
        )
    )
    next_shape_id += 1

    if image_only_layout:
        shapes.append(
            picture_xml(
                shape_id=next_shape_id,
                name="Illustration",
                x=7797800,
                y=1300000,
                cx=3850000,
                cy=2980000,
                rel_id="rId2",
            )
        )
        next_shape_id += 1
        if slide.image_caption:
            shapes.append(
                shape_xml(
                    shape_id=next_shape_id,
                    name="Image Caption",
                    x=7797800,
                    y=4375000,
                    cx=3850000,
                    cy=500000,
                    paragraphs=[
                        paragraph_xml(
                            slide.image_caption,
                            "Aptos",
                            1225,
                            "475569",
                            align="ctr",
                            line_spacing_pct=106000,
                            space_after_pts=30,
                        )
                    ],
                )
            )
            next_shape_id += 1

    if has_table and slide.table is not None:
        shapes.append(
            table_xml(
                shape_id=next_shape_id,
                x=457200,
                y=2194560,
                cx=11277600,
                cy=3901440,
                table=slide.table,
            )
        )
        next_shape_id += 1

    if has_index and slide.index_entries:
        card_entries = slide.index_entries
        rids = index_link_rids or []
        if len(rids) < len(card_entries):
            rids = rids + [""] * (len(card_entries) - len(rids))

        card_width = 5486400
        card_height = 1190000
        left_x = 457200
        right_x = left_x + card_width + 304800
        top_y = 2042160
        y_gap = 198120
        for idx, entry in enumerate(card_entries):
            col = idx % 2
            row = idx // 2
            card_x = left_x if col == 0 else right_x
            card_y = top_y + row * (card_height + y_gap)
            rid = rids[idx] if idx < len(rids) else ""
            if not rid:
                continue
            shapes.append(
                index_card_shape_xml(
                    shape_id=next_shape_id,
                    x=card_x,
                    y=card_y,
                    cx=card_width,
                    cy=card_height,
                    title=entry.label,
                    subtitle=entry.subtitle,
                    hyperlink_rid=rid,
                )
            )
            next_shape_id += 1

    if slide.code is not None:
        code_paragraphs: list[str] = []
        if slide.code_title:
            code_paragraphs.append(
                paragraph_xml(
                    slide.code_title,
                    "Aptos",
                    1400,
                    "BFDBFE",
                    bold=True,
                    line_spacing_pct=104000,
                    space_after_pts=70,
                )
            )
            code_paragraphs.append(
                paragraph_xml(
                    "",
                    "Aptos",
                    800,
                    "BFDBFE",
                    line_spacing_pct=100000,
                    space_after_pts=30,
                )
            )
        for line in slide.code.splitlines():
            code_paragraphs.append(
                paragraph_runs_xml(
                    highlight_code_line(line),
                    "Cascadia Code",
                    1200,
                    preserve=True,
                    line_spacing_pct=102000,
                    space_after_pts=30,
                )
            )
        shapes.append(
            shape_xml(
                shape_id=next_shape_id,
                name="Code",
                x=457200,
                y=3379000,
                cx=11277600,
                cy=2920000,
                paragraphs=code_paragraphs,
                fill_color="0F172A",
                line_color="334155",
                line_width=19050,
                body_pr_extra='anchor="t"',
            )
        )
        next_shape_id += 1

    if slide.footer:
        shapes.append(
            shape_xml(
                shape_id=next_shape_id,
                name="Footer",
                x=457200,
                y=6464300,
                cx=8600000,
                cy=304800,
                paragraphs=[
                    paragraph_xml(
                        slide.footer,
                        "Aptos",
                        1150,
                        "475569",
                        line_spacing_pct=100000,
                        space_after_pts=0,
                    )
                ],
            )
        )
        next_shape_id += 1

    shapes.append(
        shape_xml(
            shape_id=next_shape_id,
            name="Slide Number",
            x=9906000,
            y=6464300,
            cx=1437800,
            cy=304800,
            paragraphs=[
                paragraph_xml(
                    f"{slide_index}/{slide_count}",
                    "Aptos",
                    1150,
                    "64748B",
                    align="r",
                    line_spacing_pct=100000,
                    space_after_pts=0,
                )
            ],
        )
    )

    shape_tree = "\n".join(shapes)

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/>
          <a:ext cx="0" cy="0"/>
          <a:chOff x="0" y="0"/>
          <a:chExt cx="0" cy="0"/>
        </a:xfrm>
      </p:grpSpPr>
      {shape_tree}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>
"""


def slide_rels_xml(
    image_name: str | None = None,
    link_targets: list[int] | None = None,
) -> tuple[str, list[str]]:
    relationships = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
    ]

    next_rid = 2
    if image_name:
        relationships.append(
            f'<Relationship Id="rId{next_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{image_name}"/>'
        )
        next_rid += 1

    link_rids: list[str] = []
    for target in link_targets or []:
        rid = f"rId{next_rid}"
        next_rid += 1
        relationships.append(
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slide{target}.xml"/>'
        )
        link_rids.append(rid)

    rel_xml = "".join(relationships)
    return (
        f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rel_xml}</Relationships>
""",
        link_rids,
    )


def presentation_xml(slide_count: int) -> str:
    slide_ids = []
    rel_id = 2
    for idx in range(slide_count):
        slide_ids.append(f'<p:sldId id="{256 + idx}" r:id="rId{rel_id}"/>')
        rel_id += 1

    slide_id_lst = "".join(slide_ids)

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}" saveSubsetFonts="1" autoCompressPictures="0">
  <p:sldMasterIdLst>
    <p:sldMasterId id="2147483648" r:id="rId1"/>
  </p:sldMasterIdLst>
  <p:sldIdLst>{slide_id_lst}</p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>
  <p:notesSz cx="6858000" cy="9144000"/>
  <p:defaultTextStyle>
    <a:defPPr/>
    <a:lvl1pPr marL="0" indent="0"><a:defRPr sz="1800"/></a:lvl1pPr>
    <a:lvl2pPr marL="457200" indent="0"><a:defRPr sz="1600"/></a:lvl2pPr>
    <a:lvl3pPr marL="914400" indent="0"><a:defRPr sz="1400"/></a:lvl3pPr>
  </p:defaultTextStyle>
</p:presentation>
"""


def presentation_rels_xml(slide_count: int) -> str:
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    ]

    next_rid = 2
    for idx in range(slide_count):
        rels.append(
            f'<Relationship Id="rId{next_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{idx + 1}.xml"/>'
        )
        next_rid += 1

    rels.extend(
        [
            f'<Relationship Id="rId{next_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>',
            f'<Relationship Id="rId{next_rid + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps" Target="viewProps.xml"/>',
            f'<Relationship Id="rId{next_rid + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles" Target="tableStyles.xml"/>',
        ]
    )

    rel_xml = "".join(rels)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rel_xml}</Relationships>
"""


def content_types_xml(slide_count: int) -> str:
    slide_overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>
  <Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>
  <Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  {slide_overrides}
</Types>
"""


def root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def docprops_app_xml(slide_count: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Office PowerPoint</Application>
  <PresentationFormat>On-screen Show (16:9)</PresentationFormat>
  <Slides>{slide_count}</Slides>
  <Notes>0</Notes>
  <HiddenSlides>0</HiddenSlides>
  <MMClips>0</MMClips>
  <ScaleCrop>false</ScaleCrop>
  <HeadingPairs>
    <vt:vector size="2" baseType="variant">
      <vt:variant><vt:lpstr>Theme</vt:lpstr></vt:variant>
      <vt:variant><vt:i4>1</vt:i4></vt:variant>
    </vt:vector>
  </HeadingPairs>
  <TitlesOfParts>
    <vt:vector size="1" baseType="lpstr">
      <vt:lpstr>Case Study Theme</vt:lpstr>
    </vt:vector>
  </TitlesOfParts>
  <Company></Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>16.0000</AppVersion>
</Properties>
"""


def docprops_core_xml(now_iso: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>AAOS Persistent Contacts Cache Case Study</dc:title>
  <dc:subject>Approach comparison and recommended architecture</dc:subject>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:modified>
</cp:coreProperties>
"""


def slide_master_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">
  <p:cSld>
    <p:bg>
      <p:bgPr>
        <a:gradFill rotWithShape="1">
          <a:gsLst>
            <a:gs pos="0"><a:srgbClr val="F8FBFF"/></a:gs>
            <a:gs pos="100000"><a:srgbClr val="ECF3FF"/></a:gs>
          </a:gsLst>
          <a:lin ang="5400000" scaled="1"/>
        </a:gradFill>
        <a:effectLst/>
      </p:bgPr>
    </p:bg>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/>
          <a:ext cx="0" cy="0"/>
          <a:chOff x="0" y="0"/>
          <a:chExt cx="0" cy="0"/>
        </a:xfrm>
      </p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst>
    <p:sldLayoutId id="2147483649" r:id="rId1"/>
  </p:sldLayoutIdLst>
  <p:txStyles>
    <p:titleStyle>
      <a:lvl1pPr algn="l"><a:defRPr sz="3400" b="1"/></a:lvl1pPr>
    </p:titleStyle>
    <p:bodyStyle>
      <a:lvl1pPr marL="0" indent="0"><a:defRPr sz="1800"/></a:lvl1pPr>
      <a:lvl2pPr marL="457200" indent="0"><a:defRPr sz="1650"/></a:lvl2pPr>
    </p:bodyStyle>
    <p:otherStyle>
      <a:lvl1pPr marL="0" indent="0"><a:defRPr sz="1500"/></a:lvl1pPr>
    </p:otherStyle>
  </p:txStyles>
</p:sldMaster>
"""


def slide_layout_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}" type="blank" preserve="1">
  <p:cSld name="Blank">
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/>
          <a:ext cx="0" cy="0"/>
          <a:chOff x="0" y="0"/>
          <a:chExt cx="0" cy="0"/>
        </a:xfrm>
      </p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>
"""


def slide_master_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>
"""


def slide_layout_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>
"""


def theme_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="{NS_A}" name="Case Study Theme">
  <a:themeElements>
    <a:clrScheme name="Case Study">
      <a:dk1><a:srgbClr val="0F172A"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="1E293B"/></a:dk2>
      <a:lt2><a:srgbClr val="E2E8F0"/></a:lt2>
      <a:accent1><a:srgbClr val="2563EB"/></a:accent1>
      <a:accent2><a:srgbClr val="0F766E"/></a:accent2>
      <a:accent3><a:srgbClr val="D97706"/></a:accent3>
      <a:accent4><a:srgbClr val="0EA5E9"/></a:accent4>
      <a:accent5><a:srgbClr val="DC2626"/></a:accent5>
      <a:accent6><a:srgbClr val="7C3AED"/></a:accent6>
      <a:hlink><a:srgbClr val="2563EB"/></a:hlink>
      <a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Case Study">
      <a:majorFont><a:latin typeface="Aptos Display"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
      <a:minorFont><a:latin typeface="Aptos"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Case Study">
      <a:fillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:gradFill rotWithShape="1">
          <a:gsLst>
            <a:gs pos="0"><a:schemeClr val="phClr"><a:satMod val="103000"/><a:lumMod val="102000"/></a:schemeClr></a:gs>
            <a:gs pos="100000"><a:schemeClr val="phClr"><a:satMod val="99000"/><a:lumMod val="98000"/></a:schemeClr></a:gs>
          </a:gsLst>
          <a:lin ang="5400000" scaled="0"/>
        </a:gradFill>
        <a:gradFill rotWithShape="1">
          <a:gsLst>
            <a:gs pos="0"><a:schemeClr val="phClr"><a:lumMod val="110000"/><a:satMod val="105000"/></a:schemeClr></a:gs>
            <a:gs pos="100000"><a:schemeClr val="phClr"><a:lumMod val="100000"/><a:satMod val="100000"/></a:schemeClr></a:gs>
          </a:gsLst>
          <a:lin ang="5400000" scaled="0"/>
        </a:gradFill>
      </a:fillStyleLst>
      <a:lnStyleLst>
        <a:ln w="9525" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>
        <a:ln w="25400" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>
        <a:ln w="38100" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>
      </a:lnStyleLst>
      <a:effectStyleLst>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
      </a:effectStyleLst>
      <a:bgFillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"><a:tint val="95000"/><a:satMod val="170000"/></a:schemeClr></a:solidFill>
        <a:gradFill rotWithShape="1">
          <a:gsLst>
            <a:gs pos="0"><a:schemeClr val="phClr"><a:tint val="93000"/><a:satMod val="150000"/></a:schemeClr></a:gs>
            <a:gs pos="100000"><a:schemeClr val="phClr"><a:tint val="98000"/><a:satMod val="130000"/></a:schemeClr></a:gs>
          </a:gsLst>
          <a:lin ang="5400000" scaled="0"/>
        </a:gradFill>
      </a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
  <a:objectDefaults/>
  <a:extraClrSchemeLst/>
</a:theme>
"""


def pres_props_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentationPr xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}"/>
"""


def view_props_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:viewPr xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">
  <p:normalViewPr><p:restoredLeft sz="15620"/><p:restoredTop sz="94660"/></p:normalViewPr>
  <p:slideViewPr/>
  <p:notesTextViewPr/>
  <p:gridSpacing cx="72008" cy="72008"/>
</p:viewPr>
"""


def table_styles_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:tblStyleLst xmlns:a="{NS_A}" def="{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}"/>
"""


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


class RasterCanvas:
    def __init__(self, width: int, height: int, background: str) -> None:
        self.width = width
        self.height = height
        r, g, b = hex_to_rgb(background)
        row = bytearray(bytes((r, g, b)) * width)
        self.rows = [bytearray(row) for _ in range(height)]

    def set_pixel(self, x: int, y: int, color: str) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            r, g, b = hex_to_rgb(color)
            idx = x * 3
            self.rows[y][idx] = r
            self.rows[y][idx + 1] = g
            self.rows[y][idx + 2] = b

    def fill_vertical_gradient(self, top: str, bottom: str) -> None:
        tr, tg, tb = hex_to_rgb(top)
        br, bg, bb = hex_to_rgb(bottom)
        height_denominator = max(1, self.height - 1)
        for y in range(self.height):
            ratio = y / height_denominator
            r = int(tr + (br - tr) * ratio)
            g = int(tg + (bg - tg) * ratio)
            b = int(tb + (bb - tb) * ratio)
            self.rows[y] = bytearray(bytes((r, g, b)) * self.width)

    def fill_rect(self, x: int, y: int, width: int, height: int, color: str) -> None:
        if width <= 0 or height <= 0:
            return
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + width)
        y1 = min(self.height, y + height)
        if x0 >= x1 or y0 >= y1:
            return
        r, g, b = hex_to_rgb(color)
        fill_bytes = bytes((r, g, b)) * (x1 - x0)
        for yy in range(y0, y1):
            self.rows[yy][x0 * 3 : x1 * 3] = fill_bytes

    def draw_rect(self, x: int, y: int, width: int, height: int, color: str, thickness: int = 2) -> None:
        self.fill_rect(x, y, width, thickness, color)
        self.fill_rect(x, y + height - thickness, width, thickness, color)
        self.fill_rect(x, y, thickness, height, color)
        self.fill_rect(x + width - thickness, y, thickness, height, color)

    def fill_circle(self, cx: int, cy: int, radius: int, color: str) -> None:
        radius_sq = radius * radius
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                dx = x - cx
                dy = y - cy
                if dx * dx + dy * dy <= radius_sq:
                    self.set_pixel(x, y, color)

    def fill_rounded_rect(self, x: int, y: int, width: int, height: int, radius: int, color: str) -> None:
        radius = max(0, min(radius, width // 2, height // 2))
        self.fill_rect(x + radius, y, width - (2 * radius), height, color)
        self.fill_rect(x, y + radius, radius, height - (2 * radius), color)
        self.fill_rect(x + width - radius, y + radius, radius, height - (2 * radius), color)
        self.fill_circle(x + radius, y + radius, radius, color)
        self.fill_circle(x + width - radius - 1, y + radius, radius, color)
        self.fill_circle(x + radius, y + height - radius - 1, radius, color)
        self.fill_circle(x + width - radius - 1, y + height - radius - 1, radius, color)

    def _draw_line_single(self, x1: int, y1: int, x2: int, y2: int, color: str) -> None:
        dx = abs(x2 - x1)
        sx = 1 if x1 < x2 else -1
        dy = -abs(y2 - y1)
        sy = 1 if y1 < y2 else -1
        err = dx + dy
        while True:
            self.set_pixel(x1, y1, color)
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x1 += sx
            if e2 <= dx:
                err += dx
                y1 += sy

    def draw_line(self, x1: int, y1: int, x2: int, y2: int, color: str, thickness: int = 2) -> None:
        radius = max(0, thickness // 2)
        for ox in range(-radius, radius + 1):
            for oy in range(-radius, radius + 1):
                if ox * ox + oy * oy <= radius * radius:
                    self._draw_line_single(x1 + ox, y1 + oy, x2 + ox, y2 + oy, color)

    def to_png_bytes(self) -> bytes:
        raw = b"".join(b"\x00" + bytes(row) for row in self.rows)
        compressed = zlib.compress(raw, level=9)
        ihdr = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        return (
            b"\x89PNG\r\n\x1a\n"
            + png_chunk(b"IHDR", ihdr)
            + png_chunk(b"IDAT", compressed)
            + png_chunk(b"IEND", b"")
        )


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)


def draw_arrow(canvas: RasterCanvas, x1: int, y1: int, x2: int, y2: int, color: str) -> None:
    canvas.draw_line(x1, y1, x2, y2, color, thickness=5)
    dx = x2 - x1
    dy = y2 - y1
    length = (dx * dx + dy * dy) ** 0.5
    if length == 0:
        return
    ux = dx / length
    uy = dy / length
    px = -uy
    py = ux
    wing = 8
    tail = 14
    lx = int(x2 - (ux * tail) + (px * wing))
    ly = int(y2 - (uy * tail) + (py * wing))
    rx = int(x2 - (ux * tail) - (px * wing))
    ry = int(y2 - (uy * tail) - (py * wing))
    canvas.draw_line(x2, y2, lx, ly, color, thickness=4)
    canvas.draw_line(x2, y2, rx, ry, color, thickness=4)


def make_cover_overview_image() -> bytes:
    canvas = RasterCanvas(640, 360, "EFF6FF")
    canvas.fill_vertical_gradient("F7FAFF", "E6EEFF")
    canvas.fill_rounded_rect(44, 68, 220, 148, 16, "FFFFFF")
    canvas.draw_rect(44, 68, 220, 148, "BFDBFE", thickness=4)
    canvas.fill_rounded_rect(72, 96, 160, 70, 10, "DBEAFE")
    canvas.draw_rect(72, 96, 160, 70, "93C5FD", thickness=3)
    canvas.fill_circle(102, 192, 8, "2563EB")
    canvas.fill_circle(132, 192, 8, "0EA5E9")
    canvas.fill_circle(162, 192, 8, "38BDF8")
    canvas.fill_rounded_rect(372, 90, 210, 46, 14, "BFDBFE")
    canvas.fill_rounded_rect(362, 148, 228, 46, 14, "93C5FD")
    canvas.fill_rounded_rect(372, 206, 210, 46, 14, "60A5FA")
    canvas.draw_rect(362, 148, 228, 46, "2563EB", thickness=3)
    draw_arrow(canvas, 270, 140, 352, 128, "2563EB")
    draw_arrow(canvas, 270, 186, 352, 220, "0EA5E9")
    canvas.fill_rounded_rect(250, 250, 140, 62, 14, "FFFFFF")
    canvas.draw_rect(250, 250, 140, 62, "93C5FD", thickness=3)
    canvas.fill_circle(284, 281, 10, "0F766E")
    canvas.fill_circle(318, 281, 10, "0F766E")
    canvas.fill_circle(352, 281, 10, "0F766E")
    return canvas.to_png_bytes()


def make_problem_context_image() -> bytes:
    canvas = RasterCanvas(640, 360, "FFF7ED")
    canvas.fill_vertical_gradient("FFF7ED", "FFEDD5")
    canvas.fill_rounded_rect(62, 76, 516, 210, 20, "FFFFFF")
    canvas.draw_rect(62, 76, 516, 210, "FDBA74", thickness=4)
    canvas.fill_circle(138, 150, 34, "F59E0B")
    canvas.fill_rect(132, 132, 12, 28, "FFFFFF")
    canvas.fill_rect(132, 168, 12, 12, "FFFFFF")
    canvas.fill_circle(318, 150, 34, "F97316")
    canvas.fill_rect(312, 132, 12, 28, "FFFFFF")
    canvas.fill_rect(312, 168, 12, 12, "FFFFFF")
    canvas.fill_circle(498, 150, 34, "EF4444")
    canvas.fill_rect(492, 132, 12, 28, "FFFFFF")
    canvas.fill_rect(492, 168, 12, 12, "FFFFFF")
    draw_arrow(canvas, 180, 228, 458, 228, "FB923C")
    canvas.fill_rounded_rect(248, 248, 146, 30, 8, "FED7AA")
    canvas.draw_rect(248, 248, 146, 30, "F59E0B", thickness=2)
    return canvas.to_png_bytes()


def make_approach_fit_image() -> bytes:
    canvas = RasterCanvas(640, 360, "ECFEFF")
    canvas.fill_vertical_gradient("F0FDFF", "E0F2FE")
    node_color = "FFFFFF"
    node_border = "7DD3FC"
    canvas.fill_rounded_rect(68, 134, 150, 90, 18, node_color)
    canvas.draw_rect(68, 134, 150, 90, node_border, thickness=4)
    canvas.fill_rounded_rect(246, 96, 150, 90, 18, node_color)
    canvas.draw_rect(246, 96, 150, 90, node_border, thickness=4)
    canvas.fill_rounded_rect(246, 214, 150, 90, 18, node_color)
    canvas.draw_rect(246, 214, 150, 90, node_border, thickness=4)
    canvas.fill_rounded_rect(424, 134, 150, 90, 18, "E0F2FE")
    canvas.draw_rect(424, 134, 150, 90, "38BDF8", thickness=4)
    draw_arrow(canvas, 218, 178, 238, 142, "0EA5E9")
    draw_arrow(canvas, 218, 178, 238, 258, "0EA5E9")
    draw_arrow(canvas, 396, 142, 416, 178, "0284C7")
    draw_arrow(canvas, 396, 258, 416, 178, "0284C7")
    canvas.fill_circle(499, 178, 18, "0F766E")
    canvas.fill_circle(538, 178, 18, "0F766E")
    return canvas.to_png_bytes()


def make_rollout_timeline_image() -> bytes:
    canvas = RasterCanvas(640, 360, "F8FAFC")
    canvas.fill_vertical_gradient("F8FAFC", "EEF2FF")
    canvas.draw_line(80, 190, 560, 190, "6366F1", thickness=6)
    milestones = [(120, "93C5FD"), (280, "60A5FA"), (440, "2563EB")]
    for x, color in milestones:
        canvas.fill_circle(x, 190, 24, color)
        canvas.draw_rect(x - 52, 104, 104, 34, "A5B4FC", thickness=3)
        canvas.fill_rounded_rect(x - 48, 108, 96, 26, 8, "FFFFFF")
        draw_arrow(canvas, x, 166, x, 142, "4F46E5")
    canvas.fill_rounded_rect(96, 228, 128, 62, 12, "DBEAFE")
    canvas.fill_rounded_rect(256, 228, 128, 62, 12, "BFDBFE")
    canvas.fill_rounded_rect(416, 228, 128, 62, 12, "93C5FD")
    canvas.draw_rect(96, 228, 128, 62, "60A5FA", thickness=2)
    canvas.draw_rect(256, 228, 128, 62, "3B82F6", thickness=2)
    canvas.draw_rect(416, 228, 128, 62, "2563EB", thickness=2)
    return canvas.to_png_bytes()


def build_image_assets() -> dict[str, bytes]:
    return {
        "cover_overview": make_cover_overview_image(),
        "problem_context": make_problem_context_image(),
        "approach_fit": make_approach_fit_image(),
        "rollout_timeline": make_rollout_timeline_image(),
    }


def previous_vs_current_table() -> TableData:
    return TableData(
        headers=["Area", "Previous Approach", "Current Approach"],
        rows=[
            ["Startup UX", "Slow after reboot/disconnect", "Fast cached load before sync catch-up"],
            ["Consistency", "State can be lost after process reset", "Durable transactional state"],
            ["Sync Cost", "Frequent full sync and higher traffic", "Delta-first updates, less repeated traffic"],
            ["Read Speed", "No indexed durable query path", "Indexed, predictable read latency"],
            ["Security", "Basic controls only", "UID ACL + AES-GCM + key rotation"],
            ["Operations", "Lower recovery confidence", "Versioned migration + clear fallback"],
            ["Main Pro", "Simple initial implementation", "Reliable production behavior"],
            ["Main Con", "Unreliable restart experience", "More upfront engineering effort"],
        ],
        col_widths=[1970000, 4653800, 4653800],
    )


def three_approaches_pros_cons_table() -> TableData:
    return TableData(
        headers=["Approach", "Key Pros", "Key Cons", "Best Fit"],
        rows=[
            [
                "Approach 1: SQLite + WAL + metadata",
                "Fast indexed reads; strong transactions; migration friendly",
                "Higher upfront schema and migration complexity",
                "Production AAOS persistent contacts",
            ],
            [
                "Approach 2: JSON snapshot files",
                "Lowest initial complexity; easy manual inspection",
                "Full rewrites; weak query model; no robust transactions",
                "Prototype or very small datasets",
            ],
            [
                "Approach 3: Append-only event log",
                "Strong auditability; durable append behavior",
                "Replay/compaction overhead; slower read path at scale",
                "Audit-first, analytics-heavy systems",
            ],
        ],
        col_widths=[2020000, 3225000, 3225000, 2807600],
    )


def build_main_slides() -> list[SlideData]:
    return [
        SlideData(
            title="AAOS Persistent Contacts Cache Case Study (Main Deck)",
            bullets=[
                "This is my presentation flow for fast review and decision-making.",
                "I focus on the problem, my recommendation, and rollout readiness.",
                "I keep deep pseudocode and extended security notes in the appendix deck.",
            ],
            image_key="cover_overview",
            image_caption="Main deck: concise decision-oriented story",
            footer="Prepared on February 20, 2026",
        ),
        SlideData(
            title="Index",
            bullets=[
                "Click any card below to jump directly to that section.",
            ],
            index_entries=[
                IndexEntry(
                    label="Executive Summary",
                    subtitle="Problem, recommendation, and expected impact",
                    target_title="30-Second Executive Summary",
                ),
                IndexEntry(
                    label="Problem and Context",
                    subtitle="Current vs desired user experience",
                    target_title="Problem Context (In Simple Terms)",
                ),
                IndexEntry(
                    label="Options and Decision",
                    subtitle="Tradeoffs and why Approach 1 wins",
                    target_title="Approach Comparison (Quick)",
                ),
                IndexEntry(
                    label="Implementation and Security",
                    subtitle="Data flow, API, crypto, and fallback",
                    target_title="Data Lifecycle (End to End)",
                ),
                IndexEntry(
                    label="Metrics and Rollout",
                    subtitle="Targets, tests, libraries, and go/no-go",
                    target_title="Before vs After Metrics (Target)",
                ),
                IndexEntry(
                    label="Q&A and Backup",
                    subtitle="Likely questions and deep-dive appendix",
                    target_title="FAQ 1: Product and UX",
                ),
            ],
        ),
        SlideData(
            title="30-Second Executive Summary",
            bullets=[
                "Problem: contacts disappear after reboot/disconnect because cache is volatile.",
                "Solution: I persist contacts in SQLite with WAL and sync metadata.",
                "Security: UID access checks plus AES-GCM encryption for sensitive fields.",
                "Target impact: restart contact load p95 under 400 ms.",
                "Rollout: phased feature-flag release with automatic fallback gates.",
            ],
            image_key="approach_fit",
            image_caption="Recommendation: secure durable cache with controlled rollout",
        ),
        SlideData(
            title="Problem Context (In Simple Terms)",
            bullets=[
                "Users expect saved contacts to be ready every time they enter the car.",
                "Today, that experience breaks when process/session state is lost.",
                "Repeated full sync creates visible delay and unnecessary traffic.",
                "My objective is reliable fast access first, sync catch-up in background.",
            ],
            image_key="problem_context",
            image_caption="Volatile state causes user-visible delays and retries",
        ),
        SlideData(
            title="Current Flow (Today)",
            bullets=[
                "1. Phone connects and contacts are loaded into temporary memory.",
                "2. UI works while that process/session remains alive.",
                "3. Reboot/disconnect/process death clears temporary state.",
                "4. Next session requires a fresh, often full, sync cycle.",
                "Result: inconsistent startup experience for the driver.",
            ],
            image_key="problem_context",
            image_caption="Current flow depends too much on volatile process state",
        ),
        SlideData(
            title="Desired Flow (After My Fix)",
            bullets=[
                "1. I still ingest data from PBAP/USB adapters.",
                "2. I write normalized records into durable local cache.",
                "3. On restart, UI reads local cache immediately.",
                "4. Sync then applies only changes (delta) when available.",
                "Result: quick startup and stable contact availability.",
            ],
            image_key="cover_overview",
            image_caption="Durable cache enables fast reads before full sync catch-up",
        ),
        SlideData(
            title="Non-Negotiable Constraints",
            bullets=[
                "Correctness: no stale data overwrite, no silent mass delete on partial payloads.",
                "Security: only authorized UIDs can read/write provider data.",
                "Performance: responsive reads even during sync writes.",
                "Operations: safe schema migration and predictable rollback path.",
                "Scalability: support multi-device pairing without source collisions.",
            ],
        ),
        SlideData(
            title="Assumptions and Non-Goals",
            bullets=[
                "Assumption: source adapters eventually deliver complete and valid identifiers.",
                "Assumption: AAOS storage stack and Keystore APIs are available on target build.",
                "Assumption: UI can tolerate brief stale reads until next delta sync.",
                "Non-goal: replace upstream contacts source-of-truth semantics.",
                "Non-goal: solve cloud contact conflicts outside in-vehicle cache boundary.",
            ],
        ),
        SlideData(
            title="Approach Comparison (Quick)",
            bullets=[
                "Approach 1 - SQLite + WAL: strong consistency, fast indexed reads, migration support.",
                "Approach 2 - JSON snapshots: easiest start, weak scalability and transaction safety.",
                "Approach 3 - Event log: strong audit trail, heavier read/compaction complexity.",
                "My choice: Approach 1 for production reliability and maintainability.",
            ],
        ),
        SlideData(
            title="Pros vs Cons Table: Previous vs Current Approach",
            bullets=[
                "I summarized the practical tradeoffs between the earlier flow and my current design.",
                "This helps quickly explain why I moved to the new architecture.",
            ],
            table=previous_vs_current_table(),
        ),
        SlideData(
            title="Pros vs Cons Table: Three Approaches",
            bullets=[
                "I use this table to compare all three options side by side.",
                "It helps quickly justify why Approach 1 is my production choice.",
            ],
            table=three_approaches_pros_cons_table(),
        ),
        SlideData(
            title="Decision in One Slide",
            bullets=[
                "I recommend SQLite + WAL + sync metadata as the default architecture.",
                "It gives me deterministic writes and fast read path for UI.",
                "It aligns with AAOS provider patterns and migration practices.",
                "I accept the upfront schema effort for better long-term stability.",
            ],
            image_key="approach_fit",
            image_caption="Best tradeoff for production AAOS deployment",
        ),
        SlideData(
            title="Data Lifecycle (End to End)",
            bullets=[
                "Ingest: receive contacts from PBAP/USB adapter.",
                "Normalize: sanitize fields, dedupe records, validate payload.",
                "Protect: encrypt sensitive JSON fields before persistence.",
                "Persist: upsert/delete inside one transaction and update sync state.",
                "Serve & retain: read active rows fast, purge old tombstones async.",
            ],
            code_title="Lifecycle pseudocode",
            code="""RawContact batch
  -> normalizeAndDedupe()
  -> encryptSensitiveFields()
  -> inTransaction(applyFullOrDeltaSync)
  -> updateSyncState()
  -> queryActiveForUI()
  -> runRetentionJob()""",
        ),
        SlideData(
            title="API Contract (Sync Input/Output + Error Codes)",
            bullets=[
                "I keep API contracts explicit so source adapters and store stay decoupled.",
                "I return stable counters plus sync token for resumable sync.",
                "I use explicit error codes for recovery decisions.",
            ],
            code_title="Pseudocode: request/response contract",
            code="""final class SyncRequest {
    String sourceDevice;
    boolean fullSnapshot;
    long sourceSequence;
    String syncToken;
    List<RawContact> contacts;
    List<String> deletedIds;
}
final class SyncResponse { int inserted, updated, deleted, staleIgnored; String nextSyncToken; ErrorCode error; }""",
        ),
        SlideData(
            title="My Step-by-Step Implementation Plan",
            bullets=[
                "Step 1-2: DB bootstrap, schema, indexes, migration hooks.",
                "Step 3-5: normalize input, full sync flow, delta sync flow.",
                "Step 6-8: stale guards, read APIs, UID + encryption security.",
                "Step 9-10: retention/recovery and feature-flag rollout.",
                "I keep each step independently testable before release.",
            ],
        ),
        SlideData(
            title="Core Setup Snippet (DB + WAL + Schema Hooks)",
            bullets=[
                "I keep initialization minimal and deterministic.",
                "WAL and foreign keys are enabled at configure time.",
            ],
            code_title="Pseudocode: database helper",
            code="""@Override public void onConfigure(SQLiteDatabase db) {
    db.enableWriteAheadLogging();
    db.execSQL("PRAGMA foreign_keys=ON");
    db.execSQL("PRAGMA synchronous=NORMAL");
}
@Override public void onCreate(SQLiteDatabase db) {
    createTables(db);      // contacts + sync_state
    createIndexes(db);     // query + retention + version guards
}""",
        ),
        SlideData(
            title="Core Sync Snippet (Single Entry Point)",
            bullets=[
                "I route full and delta sync through one orchestrator function.",
                "I update sync state in the same transaction as row updates.",
            ],
            code_title="Pseudocode: sync orchestration",
            code="""SyncResult handleSync(String source, SyncPayload payload) {
    enforceWriteAccess();
    assertSequence(payload.meta(), readLastSequence(source));
    List<NormalizedContact> rows = normalizeAll(payload.contacts());
    return inTransaction(() -> {
        if (payload.meta().isFullSnapshot()) applyFullSync(source, rows, payload.meta());
        else applyDeltaSync(source, payload.delta(), payload.meta());
        upsertSyncState(source, payload.meta());
        return SyncResult.success();
    });
}""",
        ),
        SlideData(
            title="Core Read Snippet (Fast UI Path)",
            bullets=[
                "I only query active rows and decrypt only for authorized callers.",
                "I keep reads indexed and sorted for predictable UI latency.",
            ],
            code_title="Pseudocode: list API",
            code="""List<ContactView> listActive(String source, int limit) {
    return store.query(
        "source_device=? AND deleted=0",
        new String[]{source},
        "display_name COLLATE NOCASE ASC",
        limit
    ).map(row -> decryptForAuthorizedCaller(source, row));
}""",
        ),
        SlideData(
            title="Threat Model and Mitigations (1:1)",
            bullets=[
                "Unauthorized provider read -> UID allowlist + permission enforcement.",
                "Stale/out-of-order sync packet -> version and sequence guard rails.",
                "Ciphertext tampering -> AES-GCM tag validation and fail-closed behavior.",
                "PII leak in observability -> strict redaction in logs and telemetry.",
                "DB corruption -> recovery flow: clear cache + trigger fresh full sync.",
            ],
        ),
        SlideData(
            title="Encryption and Decryption Flow",
            bullets=[
                "I encrypt high-risk fields before insert/update.",
                "I use AES-GCM with random IV and AAD(source|contactId).",
                "I verify authentication tag during decrypt and fail closed on mismatch.",
            ],
            code_title="Pseudocode: field crypto",
            code="""EncryptedBlob encryptField(String source, String id, String plain, SecretKey key) {
    byte[] iv = randomBytes(12);
    Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
    c.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(128, iv));
    c.updateAAD((source + "|" + id).getBytes(UTF_8));
    return new EncryptedBlob(base64(c.doFinal(plain.getBytes(UTF_8))), base64(iv));
}
String decryptField(...) { /* same AAD + tag check; fail closed on AEADBadTagException */ }""",
        ),
        SlideData(
            title="Key Management and Rotation",
            bullets=[
                "I store AES keys in Android Keystore (non-exportable).",
                "I keep key_version per row for controlled migration.",
                "I rotate keys in small batches and promote only after verification.",
            ],
            code_title="Pseudocode: key rotation",
            code="""void rotateKeysIfDue() {
    if (!rotationPolicy.isDue(nowMs())) return;
    KeyRef next = keyManager.createNextVersion();
    for (Row row : store.rowsByKeyVersion(keyManager.currentVersion())) {
        String plain = decryptField(row.source(), row.id(), row.enc(), keyManager.currentKey());
        EncryptedBlob reenc = encryptField(row.source(), row.id(), plain, next.key());
        store.updateEncryptedPayload(row.source(), row.id(), reenc, next.version());
    }
    keyManager.promote(next);
}""",
        ),
        SlideData(
            title="Failure Scenarios and Exact Fallback Behavior",
            bullets=[
                "Sequence regression detected -> reject batch, request source recovery/full sync.",
                "AEAD tag failure on decrypt -> block row read, emit security metric, schedule recovery.",
                "Migration failure at boot -> keep legacy path enabled and retry next boot.",
                "Store transaction error -> rollback batch, preserve last consistent state.",
                "Critical cache failure rate breach -> auto-disable feature flag and fallback.",
            ],
        ),
        SlideData(
            title="Operational Runbook (When Things Go Wrong)",
            bullets=[
                "Step 1: check health dashboard (sync success, decrypt errors, migration failures).",
                "Step 2: inspect recent logs with PII-safe IDs for failing source device.",
                "Step 3: validate key alias/version availability in Keystore.",
                "Step 4: verify sequence/token progression; trigger controlled full sync if needed.",
                "Step 5: if thresholds are breached, disable feature flag and fall back safely.",
            ],
        ),
        SlideData(
            title="Before vs After Metrics (Target)",
            bullets=[
                "Cold-start contact load (p95): 2500-4000 ms -> <= 400 ms.",
                "Repeated full-sync frequency per day: high -> reduced by >= 60%.",
                "Sync success rate: baseline -> >= 99.5% steady-state.",
                "Stale overwrite incidents: non-zero risk -> 0 tolerated by design guards.",
                "Recovery time from corruption: manual/slow -> automated next sync cycle.",
            ],
            image_key="rollout_timeline",
            image_caption="Operational targets used for release decisions",
        ),
        SlideData(
            title="Cost and Effort Estimate",
            bullets=[
                "Engineering: 4-6 weeks for core implementation + integration hardening.",
                "Security: 1-2 weeks for Keystore/AES-GCM validation and threat checks.",
                "Testing: 2-3 weeks for JVM + instrumentation + migration regression matrix.",
                "Rollout/monitoring: 1-2 weeks for staged launch and observability tuning.",
                "Total estimate: 8-13 weeks depending on OEM integration dependencies.",
            ],
        ),
        SlideData(
            title="Test Coverage Matrix (Requirement -> Evidence)",
            bullets=[
                "Persistence after reopen -> `fullSync_persistsAcrossDatabaseReopen`.",
                "Delta correctness -> `deltaSync_updatesAndDeletesCorrectRows`.",
                "Partial snapshot safety -> `fullSync_partialSnapshot_doesNotDeleteMissingContacts`.",
                "Sequence guard -> `syncSequence_regressionIsRejected`.",
                "Migration/WAL/indexes -> `freshCreate_enablesWalAndCreatesRequiredIndexes`.",
                "Access control -> `enforceReadAccess_rejectsUnknownUid` + write equivalent.",
            ],
        ),
        SlideData(
            title="Libraries and Frameworks I Used",
            bullets=[
                "Storage framework: Android `SQLiteOpenHelper` + `SQLiteDatabase` + `Cursor`.",
                "Security boundary: `Binder.getCallingUid()` for provider authorization.",
                "Serialization: `org.json` for phones/emails payload handling.",
                "Crypto: Android Keystore + `Cipher` (`AES/GCM/NoPadding`).",
                "Testing: AndroidX Test (`runner`, `rules`, `core`, `ext.junit`) + JVM tests.",
                "Build setup: Gradle Kotlin DSL for instrumentation module.",
            ],
        ),
        SlideData(
            title="Go/No-Go Checklist and Rollout Plan",
            bullets=[
                "Go gate 1: cold-start load p95 <= 400 ms for target fleet.",
                "Go gate 2: sync success >= 99.5% with no critical security regressions.",
                "Go gate 3: migration pass rate >= 99.9%, rollback path validated.",
                "Rollout stages: 5% -> 25% -> 100% with automated health checks.",
                "If any gate fails, I keep fallback active and pause rollout.",
                "Detailed pseudocode/security deep dive is in the appendix deck.",
            ],
            footer="My recommendation: ship SQLite + WAL + encrypted fields after gates pass.",
            image_key="rollout_timeline",
            image_caption="Controlled rollout with objective go/no-go gates",
        ),
        SlideData(
            title="Q&A Backup (Likely Questions)",
            bullets=[
                "Q: Why not JSON snapshot for speed? A: it is simple but scales poorly and weakly transactional.",
                "Q: What if decrypt fails? A: fail closed for row, emit metric, trigger safe recovery.",
                "Q: What if migration fails in field? A: fallback remains active and retry happens next boot.",
                "Q: How is stale data prevented? A: version and sequence guard rails block regressions.",
                "Q: How do we roll back quickly? A: feature flag disable routes reads to legacy path.",
            ],
        ),
        SlideData(
            title="FAQ 1: Product and UX",
            bullets=[
                "Q: Will users notice this change immediately?",
                "A: Yes, restart/reconnect contact availability should feel significantly faster.",
                "Q: Does this replace phone contacts as source-of-truth?",
                "A: No, source device remains authoritative; this is a durable local cache.",
                "Q: What if source is temporarily offline?",
                "A: Cached contacts remain readable until sync reconnect succeeds.",
            ],
        ),
        SlideData(
            title="FAQ 2: Security and Privacy",
            bullets=[
                "Q: Are sensitive contact fields encrypted at rest?",
                "A: Yes, I encrypt high-risk fields via AES-GCM with Keystore-managed keys.",
                "Q: How is unauthorized read prevented?",
                "A: Provider entrypoints enforce UID allowlists and permission checks.",
                "Q: Can logs leak phone/email data?",
                "A: No, telemetry/logging paths use strict PII redaction.",
            ],
        ),
        SlideData(
            title="FAQ 3: Reliability and Rollout",
            bullets=[
                "Q: What if migration fails on a subset of vehicles?",
                "A: Fallback remains active and migration retries safely on next boot.",
                "Q: How do I rollback quickly in production?",
                "A: Disable feature flag to route reads to legacy path immediately.",
                "Q: How do I verify rollout safety?",
                "A: Go/no-go gates enforce latency, sync success, and migration health thresholds.",
            ],
        ),
        SlideData(
            title="Thank You",
            bullets=[
                "Thank you for reviewing my case study.",
                "Happy to answer more detailed implementation or rollout questions.",
            ],
            image_key="cover_overview",
            image_caption="End of presentation",
        ),
    ]


def build_appendix_slides() -> list[SlideData]:
    return [
        SlideData(
            title="AAOS Persistent Synced Contacts Cache Case Study",
            bullets=[
                "Project: zweithreads-case-study",
                "Scope: design and implementation options for durable Bluetooth/USB contacts",
                "Outcome: compare approaches, recommend production path, show code evidence",
            ],
            footer="Prepared on February 20, 2026",
            image_key="cover_overview",
            image_caption="System inputs and durable cache target",
        ),
        SlideData(
            title="Index",
            bullets=[
                "Click any card below to jump to the matching appendix section.",
            ],
            index_entries=[
                IndexEntry(
                    label="Plain-English Context",
                    subtitle="Problem framing and user-level explanation",
                    target_title="Quick Start (Plain English)",
                ),
                IndexEntry(
                    label="Comparison and Decision",
                    subtitle="Approach tables and recommendation",
                    target_title="Approaches Compared (High Level)",
                ),
                IndexEntry(
                    label="Implementation Pseudocode",
                    subtitle="Step-by-step design and core flows",
                    target_title="Step 1: I Initialize the Database Layer",
                ),
                IndexEntry(
                    label="Security and Reliability",
                    subtitle="Encryption, threat model, runbook, fallback",
                    target_title="My Security and Privacy Controls",
                ),
                IndexEntry(
                    label="Testing and Frameworks",
                    subtitle="Coverage evidence and stack choices",
                    target_title="How I Validate This in Tests",
                ),
                IndexEntry(
                    label="Speaker Notes and References",
                    subtitle="Presentation cues, sources, and final close",
                    target_title="Speaker Notes for Main Deck (Slides 1-11)",
                ),
            ],
        ),
        SlideData(
            title="Quick Start (Plain English)",
            bullets=[
                "This deck is about one simple problem: saved phone contacts disappear too easily.",
                "Today, contacts are often kept only in temporary memory.",
                "If the car restarts or the phone disconnects, users wait for contacts again.",
                "Our goal is to keep contacts ready so the UI opens fast every time.",
                "Think of it as moving from sticky notes to a proper filing cabinet.",
            ],
        ),
        SlideData(
            title="Why This Matters to Drivers",
            bullets=[
                "Calling a contact should feel instant, not delayed by another sync.",
                "Frequent re-sync can feel unreliable during short trips.",
                "A stable cache means fewer surprises after reboot or reconnect.",
                "Better reliability also reduces unnecessary Bluetooth/USB traffic.",
                "Simple user expectation: 'my contacts should still be there.'",
            ],
            image_key="problem_context",
            image_caption="User-visible pain comes from volatile in-memory state",
        ),
        SlideData(
            title="Current Flow (Today)",
            bullets=[
                "1. Phone connects and sends contacts to the head unit.",
                "2. Contacts are available while process and session stay alive.",
                "3. Reboot/disconnect/process death clears that temporary state.",
                "4. System must fetch everything again on the next session.",
                "Result: slow restart and repeated network/sync work.",
            ],
            image_key="problem_context",
            image_caption="Current path is fragile across restarts",
        ),
        SlideData(
            title="Desired Flow (After Fix)",
            bullets=[
                "1. Phone sync still happens, but data is also stored durably.",
                "2. On reboot, the system loads cached contacts immediately.",
                "3. Next sync sends only changes, not the full dataset each time.",
                "4. Users get fast contact access even before full background sync.",
                "Result: smoother UX, less repeated work, stronger reliability.",
            ],
            image_key="cover_overview",
            image_caption="Durable cache keeps contacts ready between sessions",
        ),
        SlideData(
            title="Decision in One Slide",
            bullets=[
                "We evaluated three storage options: SQLite, JSON files, event log.",
                "SQLite gives the best balance for speed, safety, and maintainability.",
                "JSON is simple but slows down and rewrites too much at scale.",
                "Event log is great for audit history but adds read complexity.",
                "So the recommendation is SQLite + WAL + sync metadata.",
            ],
            image_key="approach_fit",
            image_caption="SQLite is the best practical fit for production",
        ),
        SlideData(
            title="Simple Terms Used in This Deck",
            bullets=[
                "Cache: saved copy of contacts used for fast reads.",
                "Full sync: complete contact list from the phone.",
                "Delta sync: only what changed since last sync.",
                "WAL (Write-Ahead Logging): SQLite mode for safe concurrent reads/writes.",
                "Soft delete: mark removed first, physically purge later.",
            ],
        ),
        SlideData(
            title="Presentation Roadmap",
            bullets=[
                "0. Quick plain-English walkthrough (new)",
                "1. Problem and system constraints",
                "2. Approach comparison with pros and cons",
                "3. My step-by-step recommended implementation (new)",
                "4. Deep dive on SQLite + WAL architecture",
                "5. Security hardening (encryption/decryption) and framework details",
                "6. Code snippets, testing, rollout, and references",
            ],
        ),
        SlideData(
            title="Problem Context",
            bullets=[
                "Current AAOS flow keeps synced contacts only in memory.",
                "On reboot/process death/disconnect, contact state is lost.",
                "Users see cold-start delays because full re-sync is required.",
                "Repeated sync traffic adds avoidable load and battery impact.",
                "Goal: make contacts instantly available after restart while staying correct.",
            ],
            image_key="problem_context",
            image_caption="Volatile state creates restart and reliability pain",
        ),
        SlideData(
            title="Objectives and Constraints",
            bullets=[
                "Persist contacts across reboot and temporary phone disconnects.",
                "Serve list/search quickly without mandatory online sync.",
                "Support full and delta sync while preventing stale updates.",
                "Handle multi-device pairing safely with source isolation.",
                "Enforce privacy and UID-based access control in provider layer.",
                "Keep migration safe for existing users during platform upgrades.",
            ],
        ),
        SlideData(
            title="Assumptions and Non-Goals",
            bullets=[
                "Assumption: PBAP/USB adapters provide stable contact IDs eventually.",
                "Assumption: device policy allows Keystore-backed app-layer encryption.",
                "Assumption: intermittent source disconnects are expected and recoverable.",
                "Non-goal: change upstream phone contact-authoritative semantics.",
                "Non-goal: implement cloud merge/conflict engine in this cache layer.",
            ],
        ),
        SlideData(
            title="Approaches Compared (High Level)",
            bullets=[
                "Approach 1 (SQLite + WAL + sync metadata): best fit for AAOS provider patterns.",
                "Approach 2 (JSON snapshot files): simple implementation but weak scalability.",
                "Approach 3 (append-only event log): strong audit trail but costly read path.",
                "Recommendation: Approach 1 for production vehicle deployments.",
                "Tradeoff accepted: higher schema/migration work in exchange for reliability and speed.",
            ],
        ),
        SlideData(
            title="Pros vs Cons Table: Previous vs Current Approach",
            bullets=[
                "I use this as a quick side-by-side summary during discussion.",
                "Previous here means volatile/full-sync-heavy behavior before durable cache.",
            ],
            table=previous_vs_current_table(),
        ),
        SlideData(
            title="Pros vs Cons Table: Three Approaches",
            bullets=[
                "I keep a single table view so tradeoffs are easy to discuss quickly.",
                "This makes decision rationale clear for both technical and non-technical reviewers.",
            ],
            table=three_approaches_pros_cons_table(),
        ),
        SlideData(
            title="Approach 2: JSON Snapshot Cache",
            bullets=[
                "Storage model: one full JSON file per source device.",
                "Pros: smallest code surface, easy to inspect manually.",
                "Cons: every sync rewrites full payload, no transactional guarantees.",
                "Cons: read/search requires file parsing instead of indexed lookup.",
                "Verdict: useful for prototype demos only, not production AAOS.",
            ],
            code_title="Snippet: approaches/02_json_snapshot_cache/.../JsonSnapshotCache.java",
            code="""public void writeSnapshot(String sourceDevice, List<Map<String, String>> contacts) throws IOException {
    Files.createDirectories(rootDir);
    Path out = rootDir.resolve(safeName(sourceDevice) + ".json");
    // builds entire JSON payload in-memory
    Files.writeString(out, json.toString(), StandardCharsets.UTF_8);
}""",
        ),
        SlideData(
            title="Approach 3: Append-Only Event Log Cache",
            bullets=[
                "Storage model: append upsert/delete events in NDJSON stream.",
                "Pros: excellent auditability and sequential durable writes.",
                "Cons: query path depends on replay or compaction strategy.",
                "Cons: operational complexity rises with log growth.",
                "Verdict: niche choice for audit-first systems, not default AAOS path.",
            ],
            code_title="Snippet: approaches/03_event_log_cache/.../EventLogCache.java",
            code="""private void appendEvent(String sourceDevice, String type, String externalContactId, String payloadJson)
        throws IOException {
    Files.createDirectories(rootDir);
    Path file = rootDir.resolve(safeName(sourceDevice) + ".events.ndjson");
    Files.writeString(file, event, StandardCharsets.UTF_8, CREATE, APPEND);
}""",
        ),
        SlideData(
            title="Why Approach 1 Is Recommended",
            bullets=[
                "I get fast indexed reads for contact list/search/autocomplete.",
                "I can keep sync atomic using one transaction per batch.",
                "WAL lets my reads stay responsive while writes are active.",
                "SQLiteOpenHelper gives me a clean migration path by DB version.",
                "This model aligns well with existing AAOS provider patterns.",
                "The tradeoff I accept is higher upfront schema design effort.",
            ],
            image_key="approach_fit",
            image_caption="Approach 1 balances performance, correctness, and fit",
        ),
        SlideData(
            title="My Recommended Approach: Step-by-Step Plan",
            bullets=[
                "I break delivery into small steps so implementation stays predictable.",
                "Step 1: initialize SQLite DB with WAL + safe pragmas.",
                "Step 2: create contact/sync tables and indexes.",
                "Step 3: normalize input from PBAP/USB adapters.",
                "Step 4: implement full sync, then delta sync.",
                "Step 5+: add stale guards, APIs, security, retention, migration.",
            ],
            image_key="approach_fit",
            image_caption="My implementation plan from setup to rollout",
        ),
        SlideData(
            title="Data Lifecycle (End to End)",
            bullets=[
                "Ingest: receive contacts from PBAP/USB adapter.",
                "Normalize: sanitize fields, dedupe records, validate payload.",
                "Protect: encrypt sensitive JSON fields before persistence.",
                "Persist: upsert/delete in transaction and update sync state.",
                "Serve + retain: query active rows fast and purge old tombstones.",
            ],
            code_title="Lifecycle pseudocode",
            code="""RawContact batch
  -> normalizeAndDedupe()
  -> encryptSensitiveFields()
  -> inTransaction(applyFullOrDeltaSync)
  -> updateSyncState()
  -> queryActiveForUI()
  -> runRetentionJob()""",
        ),
        SlideData(
            title="API Contract (Sync Input/Output + Error Codes)",
            bullets=[
                "I keep request/response contracts explicit so adapters and store stay decoupled.",
                "I return stable counters and sync token for resumable sync.",
                "I use explicit error codes for retry/fallback behavior.",
            ],
            code_title="Pseudocode: request/response contract",
            code="""final class SyncRequest {
    String sourceDevice; boolean fullSnapshot; long sourceSequence;
    String syncToken; List<RawContact> contacts; List<String> deletedIds;
}
final class SyncResponse {
    int inserted, updated, deleted, staleIgnored;
    String nextSyncToken; ErrorCode error;
}""",
        ),
        SlideData(
            title="Step 1: I Initialize the Database Layer",
            bullets=[
                "I start by creating a dedicated SQLiteOpenHelper for cache storage.",
                "I enable WAL early so read queries stay fast during sync writes.",
                "I set safe pragmas once, then keep all writes inside transactions.",
                "This gives me a solid base before I add sync logic.",
            ],
            code_title="Pseudocode: DB bootstrap",
            code="""final class ContactsCacheDb extends SQLiteOpenHelper {
    @Override public void onConfigure(SQLiteDatabase db) {
        db.enableWriteAheadLogging();
        db.execSQL("PRAGMA foreign_keys=ON");
        db.execSQL("PRAGMA synchronous=NORMAL");
    }

    @Override public void onCreate(SQLiteDatabase db) {
        createContactsTable(db);
        createSyncStateTable(db);
        createIndexes(db);
    }
}""",
        ),
        SlideData(
            title="Step 2: I Create Schema and Indexes",
            bullets=[
                "I keep one row per (source_device, external_contact_id).",
                "I store metadata needed for conflict checks and sync resume.",
                "I keep sensitive fields encrypted at rest with per-row IV + key_version.",
                "I create indexes for list/read, retention scans, and version guards.",
                "I keep delete as a soft flag so recovery is safer.",
            ],
            code_title="Pseudocode: tables + indexes",
            code="""CREATE TABLE synced_contacts_cache (
  source_device TEXT NOT NULL, external_contact_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  phones_json_enc BLOB NOT NULL, emails_json_enc BLOB NOT NULL,
  iv BLOB NOT NULL, key_version INTEGER NOT NULL,
  source_version INTEGER NOT NULL, local_updated_ms INTEGER NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(source_device, external_contact_id)
);
CREATE INDEX idx_cache_query ON synced_contacts_cache(source_device, deleted, display_name);
CREATE INDEX idx_cache_retention ON synced_contacts_cache(source_device, local_updated_ms);""",
        ),
        SlideData(
            title="Step 3: I Normalize Input Before Writing",
            bullets=[
                "I normalize incoming records before touching the database.",
                "I trim names, sanitize phones, and dedupe by stable keys.",
                "I reject obviously bad records early and log only safe metadata.",
                "This keeps persistence clean and predictable.",
            ],
            code_title="Pseudocode: normalize + dedupe",
            code="""List<NormalizedContact> normalizeAll(List<RawContact> incoming) {
    Map<String, NormalizedContact> unique = new LinkedHashMap<>();
    for (RawContact raw : incoming) {
        if (!isValid(raw)) continue;
        NormalizedContact c = Normalizer.normalize(raw);   // trim, sanitize, map fields
        unique.put(c.externalContactId(), c);              // dedupe by source ID
    }
    return new ArrayList<>(unique.values());
}""",
        ),
        SlideData(
            title="Step 4: I Run Full Sync in One Transaction",
            bullets=[
                "For full sync, I upsert all live contacts from the source snapshot.",
                "After upserts, I soft-delete rows missing from the live ID set.",
                "I commit sync_state and data together so they never drift apart.",
                "If anything fails, I roll back the whole batch.",
            ],
            code_title="Pseudocode: full sync flow",
            code="""SyncResult applyFullSync(String source, List<NormalizedContact> rows, SyncMeta meta) {
    return inTransaction(() -> {
        Set<String> liveIds = new HashSet<>();
        for (NormalizedContact c : rows) { upsertWithStaleGuard(source, c); liveIds.add(c.externalContactId()); }
        markMissingDeleted(source, liveIds, nowMs());
        upsertSyncState(source, meta.syncToken(), meta.sequence(), nowMs());
        return SyncResult.success();
    });
}""",
        ),
        SlideData(
            title="Step 5: I Apply Delta Sync Safely",
            bullets=[
                "For delta sync, I apply only changed/new/deleted records.",
                "I never do mass delete on partial payloads from the source.",
                "I still use one transaction so updates stay atomic.",
                "I update sync_state only after row-level operations succeed.",
            ],
            code_title="Pseudocode: delta sync flow",
            code="""SyncResult applyDeltaSync(String source, DeltaPayload delta, SyncMeta meta) {
    return inTransaction(() -> {
        for (NormalizedContact c : delta.upserts()) { upsertWithStaleGuard(source, c); }
        for (String id : delta.deletedIds()) { softDelete(source, id, nowMs()); }
        upsertSyncState(source, meta.syncToken(), meta.sequence(), nowMs());
        return SyncResult.success();
    });
}""",
        ),
        SlideData(
            title="Step 6: I Block Stale or Out-of-Order Updates",
            bullets=[
                "I reject updates with lower source_version than stored rows.",
                "For equal version, I compare source_last_modified_ms.",
                "I also block sequence rollback unless explicit recovery mode is on.",
                "This prevents late packets from corrupting fresh cache data.",
            ],
            code_title="Pseudocode: stale + sequence guards",
            code="""boolean isStale(ContactPayload in, StoredRow old) {
    if (in.sourceVersion() < old.sourceVersion()) return true;
    if (in.sourceVersion() == old.sourceVersion()
            && in.sourceLastModifiedMs() < old.sourceLastModifiedMs()) return true;
    return false;
}

void assertSequence(long incoming, long lastSeen, boolean allowRecovery) {
    if (!allowRecovery && incoming < lastSeen) throw new SequenceRegressionException();
}""",
        ),
        SlideData(
            title="Step 7: I Expose Fast Read APIs for UI",
            bullets=[
                "I query only active rows (`deleted=0`) for normal contact views.",
                "I keep reads source-aware so paired devices stay isolated.",
                "I use prefix search to support fast dialer lookup.",
                "I return stable DTOs so UI code stays simple.",
            ],
            code_title="Pseudocode: list + search read path",
            code="""List<ContactView> listActive(String source, int limit) {
    return db.query(
        "source_device=? AND deleted=0",
        new String[]{source},
        "display_name COLLATE NOCASE ASC",
        limit
    );
}

List<ContactView> searchByPrefix(String source, String q) {
    return db.query("source_device=? AND deleted=0 AND display_name LIKE ?", source, q + "%");
}""",
        ),
        SlideData(
            title="Step 8: I Enforce Access + Protect PII",
            bullets=[
                "I check calling UID before allowing read/write entrypoints.",
                "I keep allowlists separate for read and write policies.",
                "I redact phone/email values in logs and metrics.",
                "I treat this as mandatory, not optional hardening.",
            ],
            code_title="Pseudocode: provider security gate",
            code="""void enforceReadAccess() {
    int uid = Binder.getCallingUid();
    if (!allowedReadUids.contains(uid)) {
        throw new SecurityException("read not allowed");
    }
}

String redactPhone(String phone) {
    return phone.length() <= 4 ? "****" : "******" + phone.substring(phone.length() - 4);
}""",
        ),
        SlideData(
            title="Step 9: I Add Retention + Recovery Jobs",
            bullets=[
                "I purge old soft-deleted rows with a background retention job.",
                "I run integrity checks and rebuild cache if corruption is detected.",
                "On recovery, I clear cache tables and trigger one fresh full sync.",
                "This keeps long-term storage healthy without user-visible failures.",
            ],
            code_title="Pseudocode: retention + corruption recovery",
            code="""void runRetention(String source, long keepMs) {
    long cutoff = nowMs() - keepMs;
    db.execSQL("DELETE FROM synced_contacts_cache WHERE source_device=? AND deleted=1 AND local_updated_ms<?",
            new Object[]{source, cutoff});
}

void recoverFromCorruption(String source) {
    clearSourceRows(source);
    clearSyncState(source);
    scheduleImmediateFullSync(source);
}""",
        ),
        SlideData(
            title="Step 10: I Roll Out with Feature Flags",
            bullets=[
                "I ship the new cache behind a runtime feature flag first.",
                "I compare metrics against legacy flow before default enablement.",
                "I keep fallback path for one release cycle for safe rollback.",
                "After stability proof, I switch the default to the new path.",
            ],
            code_title="Pseudocode: rollout gate",
            code="""ContactsResult getContacts(String source) {
    if (Flags.persistentContactsCacheEnabled()) {
        return cacheProvider.listActive(source);
    }
    return legacySessionStore.read(source);
}

void onCacheFailure(String source, Exception e) {
    Metrics.recordCacheFailure(source, e.getClass().getSimpleName());
    Flags.temporarilyDisablePersistentCache();
}""",
        ),
        SlideData(
            title="Complete Orchestrator Pseudocode (My End-to-End Flow)",
            bullets=[
                "This is the high-level function I follow for each incoming sync batch.",
                "I keep validation, transaction, metrics, and error handling in one place.",
                "This makes production behavior predictable and easy to debug.",
            ],
            code_title="Pseudocode: one sync entrypoint",
            code="""SyncResult handleIncomingSync(String source, SyncPayload payload) {
    enforceWriteAccess();
    assertSequence(payload.meta().sequence(), readLastSequence(source), payload.meta().allowRecovery());
    List<NormalizedContact> rows = normalizeAll(payload.contacts());

    SyncResult result = payload.meta().isFullSnapshot()
            ? applyFullSync(source, rows, payload.meta())
            : applyDeltaSync(source, payload.delta(), payload.meta());

    Metrics.recordSyncResult(source, result.stats());
    if (result.isCorruption()) recoverFromCorruption(source);
    return result;
}""",
        ),
        SlideData(
            title="My Recommended Architecture",
            bullets=[
                "I normalize incoming contacts from PBAP/USB adapters first.",
                "I use ContactSyncEngine to apply full or delta rules.",
                "I isolate durable writes inside ContactsCacheStore.",
                "I encrypt sensitive fields via a crypto service before persistence.",
                "I persist contacts plus per-device sync_state metadata in SQLite.",
                "I decrypt only when needed on read path for authorized callers.",
                "I serve UI from indexed active rows (`deleted=0`).",
                "I clean old tombstones asynchronously with a retention worker.",
            ],
            code_title="My architecture flow",
            code="""PBAP/USB adapters
  -> ContactSyncEngine (normalize, dedupe, sequence checks)
     -> ContactsCacheStore transaction
        -> ContactsCryptoService (encrypt/decrypt via Keystore key)
        -> synced_contacts_cache table
        -> synced_contacts_sync_state table
Provider query APIs -> indexed reads for UI
Retention job -> purge tombstones after retention window""",
        ),
        SlideData(
            title="My Data Model and Index Design",
            bullets=[
                "I use (source_device, external_contact_id) as the primary key.",
                "I store display fields plus encrypted phone/email payload columns.",
                "I persist IV and key_version to support safe decrypt + rotation.",
                "I keep last_full_sync_ms, sync token, sequence, and schema in sync_state.",
                "I index (source_device, deleted, display_name) for read speed.",
                "I index (source_device, local_updated_ms) for retention cleanup.",
                "I index source version columns for stale-update protection.",
            ],
            code_title="Snippet: approaches/01_sqlite_wal_cache/.../ContactsCacheDatabaseHelper.java",
            code="""@Override
public void onConfigure(SQLiteDatabase db) {
    db.setForeignKeyConstraintsEnabled(true);
    db.enableWriteAheadLogging();
    db.execSQL("PRAGMA synchronous=NORMAL");
}""",
        ),
        SlideData(
            title="My Sync Lifecycle: Full, Delta, and Sequence Safety",
            bullets=[
                "For full sync, I dedupe, upsert all rows, then mark missing as deleted.",
                "For delta sync, I apply only changed/new rows plus explicit deletions.",
                "I treat source_version as authority and ignore stale payloads.",
                "I reject sequence regression unless recovery mode is explicitly enabled.",
                "I record inserted/updated/deleted/stale/invalidDropped metrics every run.",
            ],
            code_title="Snippet: approaches/01_sqlite_wal_cache/.../ContactSyncEngine.java",
            code="""if (resolvedMetadata.isCompleteSnapshot()) {
    deleted = store.markMissingDeleted(normalizedSource, liveIds, nowMs);
}
store.upsertSyncState(
    normalizedSource,
    nowMs,
    resolvedMetadata.getSyncToken(),
    resolvedMetadata.getSourceSyncSequence(),
    CACHE_SCHEMA_VERSION
);""",
        ),
        SlideData(
            title="How I Block Stale Updates in Store Layer",
            bullets=[
                "I reject outdated payloads before any durable write happens.",
                "If version is equal, I still reject older source timestamps.",
                "This stops late/out-of-order packets from corrupting fresh data.",
                "I expose STALE_IGNORED in sync summary metrics for visibility.",
            ],
            code_title="Snippet: approaches/01_sqlite_wal_cache/.../SqliteContactsCacheStore.java",
            code="""if (payload.getSourceVersion() < existing.sourceVersion) {
    return UpsertOutcome.STALE_IGNORED;
}
if (payload.getSourceVersion() == existing.sourceVersion
        && payload.getSourceLastModifiedMs() < existing.sourceLastModifiedMs) {
    return UpsertOutcome.STALE_IGNORED;
}""",
        ),
        SlideData(
            title="My Security and Privacy Controls",
            bullets=[
                "I enforce UID and permission checks at provider entrypoints.",
                "I keep separate allowlists for read and write by policy.",
                "I encrypt sensitive payload fields before writing to SQLite.",
                "I use AES-GCM with random IV and AAD tied to source/contact IDs.",
                "I never log raw phone/email values in metrics or logs.",
                "I combine FBE + app-layer crypto + key rotation for defense-in-depth.",
            ],
            code_title="Snippet: access gate + encrypted write",
            code="""public void enforceReadAccess() {
    int uid = callingUidProvider.getCallingUid();
    if (!allowedReadUids.contains(uid)) {
        throw new SecurityException("UID not authorized to read cache");
    }
}

EncryptedBlob phonesEnc = crypto.encryptJson(source, contactId, phonesJson);
String redacted = PiiRedaction.redactPhone("+1 555-0102"); // ******0102""",
        ),
        SlideData(
            title="My Encryption Strategy (Layered Security)",
            bullets=[
                "Layer 1: File-based encryption (FBE) protects userdata at rest.",
                "Layer 2: I encrypt high-risk contact fields at application layer.",
                "Layer 3: UID/permission checks protect provider access.",
                "Layer 4: I redact logs/metrics and monitor failures.",
                "Layer 5: I rotate keys and support controlled re-encryption.",
            ],
            image_key="approach_fit",
            image_caption="I combine platform and app-layer controls",
        ),
        SlideData(
            title="Security Step A: I Manage Keys with Android Keystore",
            bullets=[
                "I generate and store AES keys in Android Keystore.",
                "I keep keys non-exportable and reference them by alias/version.",
                "I bind encryption policy once (AES/GCM/NoPadding, 256-bit).",
                "I treat key creation and lookup as one reusable service.",
            ],
            code_title="Pseudocode: key manager",
            code="""SecretKey getOrCreateKey(String alias) {
    KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
    ks.load(null);
    if (!ks.containsAlias(alias)) {
        KeyGenParameterSpec spec = aesGcmSpec(alias, 256);
        KeyGenerator kg = KeyGenerator.getInstance("AES", "AndroidKeyStore");
        kg.init(spec);
        kg.generateKey();
    }
    return ((KeyStore.SecretKeyEntry) ks.getEntry(alias, null)).getSecretKey();
}""",
        ),
        SlideData(
            title="Security Step B: I Encrypt Before Database Write",
            bullets=[
                "I encrypt phones/emails JSON payloads before insert/update.",
                "I generate a new random IV for each encrypted record.",
                "I use AAD (`source|contactId`) so row swaps fail authentication.",
                "I store ciphertext + IV + key_version with each row.",
            ],
            code_title="Pseudocode: encrypt on write",
            code="""EncryptedBlob encryptJson(String source, String contactId, String plainJson, SecretKey key, int keyVersion) {
    Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
    byte[] iv = SecureRandomHolder.nextBytes(12);
    c.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(128, iv));
    c.updateAAD((source + "|" + contactId).getBytes(StandardCharsets.UTF_8));
    byte[] ciphertext = c.doFinal(plainJson.getBytes(StandardCharsets.UTF_8));
    return new EncryptedBlob(base64(ciphertext), base64(iv), keyVersion);
}""",
        ),
        SlideData(
            title="Security Step C: I Decrypt Safely on Read",
            bullets=[
                "I fetch key by `key_version`, then decrypt with stored IV.",
                "I use the same AAD tuple (`source|contactId`) on decrypt.",
                "If tag verification fails, I treat it as tamper/corruption signal.",
                "I fail closed for that row and trigger recovery path if needed.",
            ],
            code_title="Pseudocode: decrypt on read",
            code="""String decryptJson(String source, String contactId, EncryptedBlob blob, SecretKey key) {
    Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
    c.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, base64Decode(blob.iv())));
    c.updateAAD((source + "|" + contactId).getBytes(StandardCharsets.UTF_8));
    try {
        byte[] plain = c.doFinal(base64Decode(blob.ciphertext()));
        return new String(plain, StandardCharsets.UTF_8);
    } catch (AEADBadTagException e) {
        throw new SecurityException("Ciphertext authentication failed", e);
    }
}""",
        ),
        SlideData(
            title="Security Step D: I Rotate Keys and Re-Encrypt",
            bullets=[
                "I rotate active encryption keys on policy interval (for example 90 days).",
                "I create new key alias/version, then re-encrypt rows in batches.",
                "I keep old key only until migration is complete and verified.",
                "After successful migration, I retire old alias safely.",
            ],
            code_title="Pseudocode: key rotation",
            code="""void rotateKeyIfNeeded(String source) {
    if (!rotationPolicy.isDue(nowMs())) return;
    KeyRef next = keyManager.createNextVersion();
    for (Row row : store.readRowsByKeyVersion(source, keyManager.currentVersion())) {
        String plain = crypto.decryptJson(source, row.contactId(), row.phonesEnc(), keyManager.currentKey());
        EncryptedBlob reenc = crypto.encryptJson(source, row.contactId(), plain, next.key(), next.version());
        store.updateEncryptedPayload(source, row.contactId(), reenc);
    }
    keyManager.promote(next);
}""",
        ),
        SlideData(
            title="My Performance and Reliability Strategy",
            bullets=[
                "I use WAL so reads stay responsive during write-heavy sync.",
                "I use one transaction per batch to avoid partial commits.",
                "I soft-delete first and purge later for safer recovery.",
                "I block mass delete behavior for partial source snapshots.",
                "I apply quotas and normalization to contain bad payloads.",
                "I include corruption recovery to reset and trigger full sync.",
            ],
        ),
        SlideData(
            title="How I Validate This in Tests",
            bullets=[
                "I run JVM tests for core sync logic without Android runtime.",
                "I run integration tests for real SQLite behavior on Android.",
                "I cover reopen persistence, delta conflicts, and sequence regressions.",
                "I verify v1->v2 migration creates indexes and keeps WAL enabled.",
                "I test access enforcement for both allow and deny paths.",
            ],
            code_title="Snippet: instrumentation migration validation",
            code="""try (Cursor cursor = db.rawQuery("PRAGMA journal_mode", null)) {
    assertTrue(cursor.moveToFirst());
    String mode = cursor.getString(0);
    assertEquals("wal", mode.toLowerCase());
}
assertTrue(hasIndex(db, ContactsCacheContract.INDEX_SOURCE_VERSION));""",
        ),
        SlideData(
            title="Threat Model and Mitigations (1:1)",
            bullets=[
                "Unauthorized provider read -> UID allowlist + permission enforcement.",
                "Stale/out-of-order packet -> version and sequence guard checks.",
                "Ciphertext tampering -> AES-GCM authentication tag verification.",
                "PII leak in logs -> strict redaction policy in telemetry/logging.",
                "DB corruption -> fail-safe recovery (clear cache + full sync).",
            ],
        ),
        SlideData(
            title="Failure Scenarios and Fallback Behavior",
            bullets=[
                "Sequence regression -> reject batch and request source recovery/full sync.",
                "AEAD decrypt failure -> fail closed for row and schedule recovery.",
                "Migration failure -> keep legacy path enabled, retry on next boot.",
                "Transaction failure -> rollback full batch and keep last consistent state.",
                "Health gate breach -> auto-disable feature flag and fallback.",
            ],
        ),
        SlideData(
            title="Operational Runbook",
            bullets=[
                "1. Check health metrics: sync success, stale drops, decrypt failures, migration errors.",
                "2. Identify impacted source_device(s) and inspect redacted logs.",
                "3. Validate key alias/version presence and decrypt test for sampled row.",
                "4. Trigger controlled full sync if sequence/token state looks inconsistent.",
                "5. If error budget breached, disable flag and route to legacy path.",
            ],
        ),
        SlideData(
            title="Before vs After Metrics (Target)",
            bullets=[
                "Cold-start load p95: 2500-4000 ms -> <= 400 ms.",
                "Repeated full-sync frequency: reduced by >= 60%.",
                "Sync success rate: target >= 99.5%.",
                "Stale overwrite incidents: target 0 by guard design.",
                "Corruption recovery: automated within next sync cycle.",
            ],
            image_key="rollout_timeline",
            image_caption="Operational targets for production readiness",
        ),
        SlideData(
            title="Cost and Effort Estimate",
            bullets=[
                "Core implementation + integration: 4-6 engineer weeks.",
                "Security hardening and validation: 1-2 engineer weeks.",
                "Test expansion and migration regression matrix: 2-3 engineer weeks.",
                "Rollout and observability tuning: 1-2 engineer weeks.",
                "Overall: 8-13 weeks depending on integration and OEM dependencies.",
            ],
        ),
        SlideData(
            title="Test Coverage Matrix (Requirement -> Evidence)",
            bullets=[
                "Persistence after reopen -> fullSync_persistsAcrossDatabaseReopen.",
                "Delta correctness -> deltaSync_updatesAndDeletesCorrectRows.",
                "Partial snapshot safety -> fullSync_partialSnapshot_doesNotDeleteMissingContacts.",
                "Sequence guard -> syncSequence_regressionIsRejected.",
                "Migration/WAL/indexes -> freshCreate_enablesWalAndCreatesRequiredIndexes.",
                "Access control -> enforceReadAccess_rejectsUnknownUid (and write equivalent).",
            ],
        ),
        SlideData(
            title="Libraries and Concepts I Use",
            bullets=[
                "Android Framework (runtime): SQLiteOpenHelper, SQLiteDatabase, Cursor, ContentValues, Binder.",
                "Java/JDK: collections, immutable value objects, time utilities, exception handling.",
                "JSON handling: org.json JSONArray for phone/email payload encoding.",
                "Security APIs: Android Keystore + javax.crypto Cipher (AES/GCM).",
                "Testing stack: JVM unit tests + AndroidX Test instrumentation suite.",
                "I keep core sync logic separate from Android persistence details.",
            ],
        ),
        SlideData(
            title="Frameworks and Libraries I Used (Detailed Mapping)",
            bullets=[
                "Storage framework: Android SQLite APIs (`SQLiteOpenHelper`, `SQLiteDatabase`).",
                "IPC/security boundary: Binder UID checks via `Binder.getCallingUid()`.",
                "Serialization layer: `org.json` to persist multi-value fields consistently.",
                "Testing framework: AndroidX Test Runner/Rules/Core + JUnit extension.",
                "Crypto layer: Android Keystore for keys + AES-GCM via `Cipher`.",
                "Build/testing setup: Gradle Kotlin DSL in instrumentation module.",
            ],
            code_title="Pseudocode: component-to-library map",
            code="""ContactsProvider API
  -> ContactsCacheAccessEnforcer (Binder UID check)
  -> ContactSyncEngine (core logic)
  -> SqliteContactsCacheStore (SQLiteDatabase)
       -> JSON serialization (org.json)
       -> Crypto service (Android Keystore + Cipher AES/GCM)
  -> AndroidX instrumentation tests (runner/rules/core/ext.junit)""",
        ),
        SlideData(
            title="Actual Testing Dependencies I Use",
            bullets=[
                "I kept the testing stack simple and explicit in Gradle.",
                "I use AndroidX Test runner/rules/core plus JUnit extension.",
                "This gives me stable on-device verification for migration + store behavior.",
                "I run these alongside JVM tests for quick feedback loops.",
            ],
            code_title="Snippet: instrumentation-tests/build.gradle.kts",
            code="""dependencies {
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test:rules:1.6.1")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:core:1.6.1")
    androidTestImplementation("androidx.annotation:annotation:1.9.1")
}""",
        ),
        SlideData(
            title="Why I Chose These Frameworks",
            bullets=[
                "I chose SQLite APIs because they match AAOS/AOSP provider patterns directly.",
                "I used Binder UID checks because provider access control is mandatory in-system.",
                "I used org.json because phone/email arrays map naturally to JSON payloads.",
                "I used AndroidX Test because it validates real Android runtime behavior.",
                "I use Keystore + AES-GCM because confidentiality + integrity are both required.",
            ],
        ),
        SlideData(
            title="My Migration and Rollout Plan",
            bullets=[
                "Phase 1 (weeks 1-2): I add schema + sync engine behind a feature flag.",
                "Phase 2 (weeks 3-4): I wire PBAP/USB, telemetry, and permission hardening.",
                "Phase 3 (weeks 5-6): I dogfood, benchmark, and enable by default.",
                "For upgrade, I create tables/indexes in one migration transaction.",
                "If migration fails, I fall back and retry next boot safely.",
                "I keep one release cycle with fallback before deprecating legacy path.",
            ],
            image_key="rollout_timeline",
            image_caption="Three-phase rollout with guarded fallback",
        ),
        SlideData(
            title="Go/No-Go Checklist",
            bullets=[
                "Go gate 1: cold-start load p95 <= 400 ms on target fleet.",
                "Go gate 2: sync success >= 99.5% with no critical security regressions.",
                "Go gate 3: migration pass rate >= 99.9% and rollback validated.",
                "Rollout stages: 5% -> 25% -> 100% with health checks at each stage.",
                "If any gate fails, I keep fallback enabled and pause rollout.",
            ],
            footer="Release decision is metric-gated, not assumption-gated.",
        ),
        SlideData(
            title="My Pros and Cons Summary",
            bullets=[
                "Approach 1 pros for me: speed, consistency, migration safety, AAOS fit.",
                "Approach 1 cons: more upfront engineering work.",
                "Approach 2 pros: easiest implementation and readable files.",
                "Approach 2 cons: full rewrites and weak query behavior at scale.",
                "Approach 3 pros: strong auditability and durable append log.",
                "Approach 3 cons: replay/compaction burden and slower read path.",
            ],
            footer="My decision: use Approach 1 as the production default.",
        ),
        SlideData(
            title="How I Explain This Case Study",
            bullets=[
                "I start with user pain: contacts disappear and restart feels slow.",
                "Then I show 3 options to explain tradeoffs clearly.",
                "I spend most time on Approach 1 because it is production-ready.",
                "I show code snippets to prove this is implemented, not theoretical.",
                "I close with tests, rollout steps, and risk mitigation.",
            ],
        ),
        SlideData(
            title="Q&A Backup",
            bullets=[
                "Q: Why not keep JSON snapshots? A: simple start, but poor scale and query behavior.",
                "Q: How do I prevent stale overwrite? A: strict version + sequence guard checks.",
                "Q: What happens on decrypt failure? A: fail closed, metric, recovery path.",
                "Q: How do I roll back quickly? A: feature-flag fallback to legacy read path.",
                "Q: Is key rotation disruptive? A: no, batched re-encryption with key_version tracking.",
            ],
        ),
        SlideData(
            title="Speaker Notes for Main Deck (Slides 1-11)",
            bullets=[
                "Slides 1-3: open with cover, index, and decision frame.",
                "Slides 4-6: explain user pain and desired post-fix experience.",
                "Slides 7-8: state constraints and assumptions clearly.",
                "Slides 9-11: compare options and justify Approach 1.",
                "Narration cue: emphasize reliability + rollback confidence early.",
            ],
        ),
        SlideData(
            title="Speaker Notes for Main Deck (Slides 12-21)",
            bullets=[
                "Slides 12-15: walk through lifecycle, API contract, and core code flow.",
                "Slides 16-18: cover threat model, crypto flow, and key rotation briefly.",
                "Slides 19-21: explain fallback behavior and operational runbook actions.",
                "Narration cue: avoid deep crypto internals unless asked.",
                "Narration cue: tie each technical point back to user-visible impact.",
            ],
        ),
        SlideData(
            title="Speaker Notes for Main Deck (Slides 22-29)",
            bullets=[
                "Slides 22-24: present metrics, effort estimate, and test evidence.",
                "Slides 25-29: summarize stack choices, rollout gates, and likely questions.",
                "Slides 30-33: use FAQ pages and thank-you close for interaction.",
                "Narration cue: keep close under 60 seconds with explicit ask.",
                "Narration cue: keep appendix ready for deep-dive questions.",
            ],
        ),
        SlideData(
            title="Repository References",
            bullets=[
                "- docs/AAOS_Persistent_Contacts_Case_Study.md",
                "- approaches/01_sqlite_wal_cache/BEST_APPROACH_STUDY.md",
                "- approaches/01_sqlite_wal_cache/PRODUCTION_DEPLOYMENT_GUIDE.md",
                "- approaches/01_sqlite_wal_cache/aosp_patch/CONTACTS_PROVIDER_PATCH_PLAN.md",
                "- approaches/01_sqlite_wal_cache/src/main/java/...",
                "- approaches/02_json_snapshot_cache/src/main/java/...",
                "- approaches/03_event_log_cache/src/main/java/...",
            ],
        ),
        SlideData(
            title="Platform and Security References",
            bullets=[
                "- https://developer.android.com/reference/android/database/sqlite/SQLiteOpenHelper",
                "- https://developer.android.com/reference/android/os/Binder#getCallingUid()",
                "- https://developer.android.com/privacy-and-security/keystore",
                "- https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec",
                "- https://developer.android.com/reference/javax/crypto/Cipher",
                "- https://source.android.com/docs/security/features/encryption/file-based",
            ],
        ),
        SlideData(
            title="My Final Recommendation",
            bullets=[
                "I recommend SQLite + WAL + sync metadata as the production baseline.",
                "I keep JSON snapshot and event log variants as prototype references.",
                "I prioritize migration safety, access controls, and instrumentation.",
                "This repo gives me a strong base for AAOS integration rollout.",
            ],
            footer="End of my case study deck",
        ),
        SlideData(
            title="FAQ 1: Product and UX",
            bullets=[
                "Q: Will users notice this immediately?",
                "A: Yes, startup/reconnect contact experience should be much faster.",
                "Q: Does this replace source-of-truth semantics?",
                "A: No, source device remains authoritative; cache is local acceleration.",
                "Q: What if source disconnects often?",
                "A: Cache serves last valid state and sync resumes on reconnect.",
            ],
        ),
        SlideData(
            title="FAQ 2: Security and Privacy",
            bullets=[
                "Q: How is sensitive data protected at rest?",
                "A: AES-GCM encryption with Keystore-backed key management.",
                "Q: How is unauthorized access blocked?",
                "A: UID allowlists and permission checks at provider boundary.",
                "Q: Is observability production-safe?",
                "A: Yes, PII is redacted in logs and telemetry.",
            ],
        ),
        SlideData(
            title="FAQ 3: Rollout and Reliability",
            bullets=[
                "Q: What if metrics degrade during rollout?",
                "A: Go/no-go gates stop rollout and fallback can be enabled immediately.",
                "Q: How do we recover from decrypt/migration failures?",
                "A: Fail closed, emit metrics, run controlled recovery and full sync.",
                "Q: How quickly can we revert?",
                "A: Runtime flag rollback is immediate.",
            ],
        ),
        SlideData(
            title="Thank You",
            bullets=[
                "Thank you for your time and feedback.",
                "I’m ready for deep-dive questions on implementation, security, or rollout.",
            ],
            image_key="cover_overview",
            image_caption="End of appendix",
        ),
    ]


def generate_pptx(output_path: Path, slides: list[SlideData]) -> None:
    image_assets = build_image_assets()
    image_names = {key: f"image{idx}.png" for idx, key in enumerate(sorted(image_assets.keys()), start=1)}
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    title_to_index = {slide.title: idx for idx, slide in enumerate(slides, start=1)}

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml(len(slides)))
        zf.writestr("_rels/.rels", root_rels_xml())

        zf.writestr("docProps/app.xml", docprops_app_xml(len(slides)))
        zf.writestr("docProps/core.xml", docprops_core_xml(now_iso))

        zf.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        zf.writestr("ppt/_rels/presentation.xml.rels", presentation_rels_xml(len(slides)))

        zf.writestr("ppt/presProps.xml", pres_props_xml())
        zf.writestr("ppt/viewProps.xml", view_props_xml())
        zf.writestr("ppt/tableStyles.xml", table_styles_xml())

        zf.writestr("ppt/theme/theme1.xml", theme_xml())
        zf.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels_xml())
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels_xml())

        for image_key, image_bytes in image_assets.items():
            zf.writestr(f"ppt/media/{image_names[image_key]}", image_bytes)

        for idx, slide in enumerate(slides, start=1):
            image_name = image_names.get(slide.image_key, None) if slide.image_key else None
            link_targets: list[int] = []
            if slide.index_entries:
                for entry in slide.index_entries:
                    target_idx = title_to_index.get(entry.target_title)
                    if target_idx is not None:
                        link_targets.append(target_idx)

            rel_xml, link_rids = slide_rels_xml(image_name, link_targets)
            zf.writestr(f"ppt/slides/slide{idx}.xml", slide_xml(slide, idx, len(slides), index_link_rids=link_rids))
            zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", rel_xml)


if __name__ == "__main__":
    main_out = Path("docs/AAOS_Persistent_Contacts_Case_Study_Presentation.pptx")
    appendix_out = Path("docs/AAOS_Persistent_Contacts_Case_Study_Presentation_Appendix.pptx")

    generate_pptx(main_out, build_main_slides())
    generate_pptx(appendix_out, build_appendix_slides())

    print(main_out)
    print(appendix_out)
