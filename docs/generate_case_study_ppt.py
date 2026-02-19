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


@dataclass(frozen=True)
class RunData:
    text: str
    color: str
    bold: bool = False
    italic: bool = False


def run_xml(
    text: str,
    font: str,
    size: int,
    color: str,
    bold: bool = False,
    italic: bool = False,
    preserve: bool = False,
) -> str:
    attrs = [f'lang="en-US"', f'sz="{size}"']
    if bold:
        attrs.append('b="1"')
    if italic:
        attrs.append('i="1"')
    text_attrs = ' xml:space="preserve"' if preserve else ""
    return (
        f"<a:r><a:rPr {' '.join(attrs)}><a:solidFill><a:srgbClr val=\"{color}\"/>"
        f"</a:solidFill><a:latin typeface=\"{font}\"/></a:rPr>"
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
) -> str:
    ppr = f'<a:pPr algn="{align}"/>' if align else ""
    if text == "":
        return f"<a:p>{ppr}<a:endParaRPr lang=\"en-US\" sz=\"{size}\"/></a:p>"
    run = run_xml(text, font, size, color, bold=bold, italic=italic, preserve=preserve)
    return f"<a:p>{ppr}{run}<a:endParaRPr lang=\"en-US\" sz=\"{size}\"/></a:p>"


def paragraph_runs_xml(
    runs: Iterable[RunData],
    font: str,
    size: int,
    preserve: bool = False,
    align: str | None = None,
) -> str:
    ppr = f'<a:pPr algn="{align}"/>' if align else ""
    run_xml_parts = [
        run_xml(
            run.text,
            font,
            size,
            run.color,
            bold=run.bold,
            italic=run.italic,
            preserve=preserve,
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

    return f"""
<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="{escape(name)}"/>
    <p:cNvSpPr/>
    <p:nvPr/>
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


def slide_xml(slide: SlideData, slide_index: int, slide_count: int) -> str:
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
            paragraphs=[paragraph_xml(slide.title, "Aptos Display", 3400, "0F172A", bold=True)],
        )
    )
    next_shape_id += 1

    image_only_layout = slide.image_key is not None and slide.code is None
    body_height = 5003800 if slide.code is None else 2300000
    body_x = 457200
    body_y = 914400
    body_width = 7073900 if image_only_layout else 11277600
    body_size = 1725 if image_only_layout else 1825

    body_paragraphs = [
        paragraph_xml(format_body_line(line), "Aptos", body_size, "1E293B") for line in slide.bullets
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
                    paragraphs=[paragraph_xml(slide.image_caption, "Aptos", 1225, "475569", align="ctr")],
                )
            )
            next_shape_id += 1

    if slide.code is not None:
        code_paragraphs: list[str] = []
        if slide.code_title:
            code_paragraphs.append(paragraph_xml(slide.code_title, "Aptos", 1400, "BFDBFE", bold=True))
            code_paragraphs.append(paragraph_xml("", "Aptos", 800, "BFDBFE"))
        for line in slide.code.splitlines():
            code_paragraphs.append(paragraph_runs_xml(highlight_code_line(line), "Cascadia Code", 1200, preserve=True))
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
                paragraphs=[paragraph_xml(slide.footer, "Aptos", 1150, "475569")],
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
            paragraphs=[paragraph_xml(f"{slide_index}/{slide_count}", "Aptos", 1150, "64748B", align="r")],
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


def slide_rels_xml(image_name: str | None = None) -> str:
    image_rel = ""
    if image_name:
        image_rel = (
            f'\n  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="../media/{image_name}"/>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>{image_rel}
</Relationships>
"""


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


def build_slides() -> list[SlideData]:
    return [
        SlideData(
            title="AAOS Persistent Synced Contacts Cache Case Study",
            bullets=[
                "Project: zweithreads-case-study",
                "Scope: design and implementation options for durable Bluetooth/USB contacts",
                "Outcome: compare approaches, recommend production path, show code evidence",
            ],
            footer="Prepared on February 18, 2026",
            image_key="cover_overview",
            image_caption="System inputs and durable cache target",
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
                "3. Deep dive on recommended SQLite + WAL architecture",
                "4. Code snippets from repository implementation",
                "5. Libraries, concepts, testing, rollout, and references",
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
                "Fast indexed reads for contact list/search/autocomplete.",
                "Transactional correctness for full/delta sync batches.",
                "WAL supports concurrent reads during sync writes.",
                "Natural migration model via SQLiteOpenHelper DB versions.",
                "Strong AAOS/AOSP compatibility with ContactsProvider patterns.",
                "Main cost: upfront schema and migration engineering effort.",
            ],
            image_key="approach_fit",
            image_caption="Approach 1 balances performance, correctness, and fit",
        ),
        SlideData(
            title="Recommended Architecture",
            bullets=[
                "Source adapters (PBAP/USB) normalize incoming contacts.",
                "ContactSyncEngine applies full or delta sync rules.",
                "ContactsCacheStore abstracts transactional persistence.",
                "SQLite tables store contacts plus per-device sync_state metadata.",
                "Read APIs query active contacts (deleted=0) through indexes.",
                "Retention worker purges old soft-deleted rows asynchronously.",
            ],
            code_title="Flow",
            code="""PBAP/USB adapters
  -> ContactSyncEngine (normalize, dedupe, sequence checks)
     -> ContactsCacheStore transaction
        -> synced_contacts_cache table
        -> synced_contacts_sync_state table
Provider query APIs -> indexed reads for UI
Retention job -> purge tombstones after retention window""",
        ),
        SlideData(
            title="Data Model and Index Design",
            bullets=[
                "Primary key: (source_device, external_contact_id) for multi-device isolation.",
                "contact fields include display data, phones_json, emails_json, versions, timestamps, deleted.",
                "sync_state keeps last_full_sync_ms, token, source sequence, schema version.",
                "Index 1: (source_device, deleted, display_name) for query speed.",
                "Index 2: (source_device, local_updated_ms) for retention scans.",
                "Index 3: (source_device, source_version, source_last_modified_ms) for version guards.",
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
            title="Sync Lifecycle: Full, Delta, and Sequence Safety",
            bullets=[
                "Full sync: dedupe incoming records, upsert all, delete missing only on complete snapshot.",
                "Delta sync: upsert changed/new, apply explicit deletions.",
                "Conflict rule: source_version is authoritative; stale updates are ignored.",
                "Sequence rule: reject sourceSyncSequence regressions unless recovery is allowed.",
                "Outcome metrics include inserted/updated/deleted/stale/invalidDropped.",
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
            title="Stale Update Protection in Store Layer",
            bullets=[
                "Store rejects outdated payloads before touching durable state.",
                "Same-version but older timestamp is also ignored.",
                "This prevents late/out-of-order source data from corrupting cache.",
                "Result category STALE_IGNORED is surfaced in sync summary metrics.",
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
            title="Security and Privacy Controls",
            bullets=[
                "Provider entrypoints should enforce UID and permission checks.",
                "Read and write UID sets can be separated by policy.",
                "Logs and telemetry should avoid raw phone/email payloads.",
                "FBE-backed userdata gives baseline at-rest protection.",
                "Optional stronger encryption can be added for strict OEM policy.",
            ],
            code_title="Snippet: access enforcement and PII redaction",
            code="""public void enforceReadAccess() {
    int uid = callingUidProvider.getCallingUid();
    if (!allowedReadUids.contains(uid)) {
        throw new SecurityException("UID not authorized to read cache");
    }
}

String redacted = PiiRedaction.redactPhone("+1 555-0102"); // ******0102""",
        ),
        SlideData(
            title="Performance and Reliability Strategy",
            bullets=[
                "WAL mode keeps reads responsive during write-heavy sync batches.",
                "One transaction per sync batch avoids partial state commits.",
                "Soft-delete first, purge later: safer than immediate hard delete.",
                "Partial snapshot mode prevents accidental mass deletions.",
                "Quota limits and input normalization protect against bad payloads.",
                "Corruption recovery path: reset cache tables and trigger full sync.",
            ],
        ),
        SlideData(
            title="Testing Evidence in Repository",
            bullets=[
                "JVM tests validate core logic without Android runtime dependency.",
                "Integration tests validate real SQLite behavior on Android runtime.",
                "Covered scenarios: persistence after reopen, delta conflicts, sequence regression.",
                "Migration test verifies v1->v2 index creation and WAL mode.",
                "Access enforcer tests verify authorization failures and allowed paths.",
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
            title="Libraries and Concepts Used",
            bullets=[
                "Android APIs: SQLiteOpenHelper, SQLiteDatabase, Cursor, ContentValues, Binder.",
                "Java APIs: java.util collections, java.nio.file IO, immutable value models.",
                "JSON handling: org.json JSONArray for phone/email persistence encoding.",
                "Testing: custom JVM runner plus AndroidX Test (runner/rules/core/ext.junit).",
                "Core concepts: WAL, transactional sync, soft delete, schema migration, UID ACL.",
                "Architecture concept: clean split between core sync logic and Android persistence layer.",
            ],
        ),
        SlideData(
            title="Migration and Rollout Plan",
            bullets=[
                "Phase 1 (weeks 1-2): add schema + sync engine behind feature flag.",
                "Phase 2 (weeks 3-4): integrate PBAP/USB adapters, telemetry, permission hardening.",
                "Phase 3 (weeks 5-6): dogfood rollout, benchmark, enable by default.",
                "Upgrade path: create tables/indexes in one DB migration transaction.",
                "Failure handling: fallback to legacy path and retry migration next boot.",
                "Keep one release cycle with fallback before full deprecation.",
            ],
            image_key="rollout_timeline",
            image_caption="Three-phase rollout with guarded fallback",
        ),
        SlideData(
            title="Pros and Cons Summary",
            bullets=[
                "Approach 1 pros: performance, consistency, migration safety, AAOS fit.",
                "Approach 1 cons: higher initial engineering complexity.",
                "Approach 2 pros: easiest implementation, readable files.",
                "Approach 2 cons: full rewrites, weak query model, no robust transactions.",
                "Approach 3 pros: strong auditability and append durability.",
                "Approach 3 cons: replay/compaction burden and slower read path at scale.",
            ],
            footer="Decision: use Approach 1 as default production architecture.",
        ),
        SlideData(
            title="How to Present This as a Case Study",
            bullets=[
                "Start with user pain: contacts disappear and cold-start is slow.",
                "Show 3 alternatives briefly to demonstrate architecture tradeoff thinking.",
                "Spend most time on Approach 1 and why it is production-ready.",
                "Use code snippets to prove correctness mechanisms are implemented, not theoretical.",
                "Close with test evidence, rollout plan, and risk mitigation to show delivery readiness.",
            ],
        ),
        SlideData(
            title="References",
            bullets=[
                "Repository docs:",
                "- docs/AAOS_Persistent_Contacts_Case_Study.md",
                "- approaches/01_sqlite_wal_cache/BEST_APPROACH_STUDY.md",
                "- approaches/01_sqlite_wal_cache/PRODUCTION_DEPLOYMENT_GUIDE.md",
                "- approaches/01_sqlite_wal_cache/aosp_patch/CONTACTS_PROVIDER_PATCH_PLAN.md",
                "Repository code:",
                "- approaches/01_sqlite_wal_cache/src/main/java/...",
                "- approaches/02_json_snapshot_cache/src/main/java/...",
                "- approaches/03_event_log_cache/src/main/java/...",
                "Android references:",
                "- https://developer.android.com/reference/android/database/sqlite/SQLiteOpenHelper",
                "- https://developer.android.com/reference/android/os/Binder#getCallingUid()",
                "- https://source.android.com/docs/security/features/encryption/file-based",
            ],
        ),
        SlideData(
            title="Final Recommendation",
            bullets=[
                "Adopt SQLite + WAL + sync metadata as the production baseline.",
                "Keep JSON snapshot and event log variants as learning/prototype options.",
                "Prioritize migration safety, access controls, and instrumentation in rollout.",
                "This repo already provides a strong foundation for AAOS integration.",
            ],
            footer="End of case study deck",
        ),
    ]


def generate_pptx(output_path: Path) -> None:
    slides = build_slides()
    image_assets = build_image_assets()
    image_names = {key: f"image{idx}.png" for idx, key in enumerate(sorted(image_assets.keys()), start=1)}
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

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
            zf.writestr(f"ppt/slides/slide{idx}.xml", slide_xml(slide, idx, len(slides)))
            zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", slide_rels_xml(image_name))


if __name__ == "__main__":
    out = Path("docs/AAOS_Persistent_Contacts_Case_Study_Presentation.pptx")
    generate_pptx(out)
    print(out)
