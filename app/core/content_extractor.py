from bs4 import BeautifulSoup, Tag
from app.models.schemas import SvgData, ImgData


def get_page_title(soup: BeautifulSoup) -> str | None:
    return soup.title.get_text(strip=True) if soup.title else None


def get_aria_described_by(tag: Tag, soup: BeautifulSoup) -> str | None:
    id_ = tag.get('aria-describedby')
    if not id_:
        return None
    desc_tag = soup.find(id=id_)
    return desc_tag.get_text(strip=True) if desc_tag else None

def get_section_heading(tag: Tag) -> str | None:
    for ancestor in tag.parents:
        heading = ancestor.find_previous_sibling(
            lambda t: t.name in ('h1','h2','h3','h4','h5','h6')
        )
        if heading:
            return heading.get_text(strip=True)
    return None

def get_figure_caption(tag: Tag) -> str | None:
    figure = tag.find_parent('figure')
    if not figure:
        return None
    figcaption = figure.find('figcaption')
    return figcaption.get_text(strip=True) if figcaption else None

def get_nearby_paragraph(tag: Tag) -> str | None:
    container = tag.find_parent(['div', 'section', 'article', 'figure', 'td'])
    if container:
        para = container.find('p')
        if para:
            return para.get_text(strip=True)[:300]
    for sibling in tag.next_siblings:
        if hasattr(sibling, 'get_text'):
            text = sibling.get_text(strip=True)
            if text:
                return text[:300]
    return None

def build_parent_context(page_title: str | None, tag: Tag) -> str | None:
    parts = []
    if page_title:
        parts.append(f"Page title: {page_title}")
    heading = get_section_heading(tag)
    if heading:
        parts.append(f"Section heading: {heading}")
    para = get_nearby_paragraph(tag)
    if para:
        parts.append(f"Nearby paragraph: {para}")
    caption = get_figure_caption(tag)
    if caption:
        parts.append(f"Figure caption: {caption}")
    return "\n".join(parts) or None


def extract_svg(tag: Tag, soup: BeautifulSoup, page_title: str | None) -> SvgData:
    ariaLabel = tag.get('aria-label')
    return SvgData(
        html=str(tag),
        ariaLabel=ariaLabel[0] if ariaLabel else '',
        ariaDescribedBy=get_aria_described_by(tag, soup),
        parentContext=build_parent_context(page_title, tag),
    )

# def extract_img(tag: Tag, soup: BeautifulSoup, page_title: str | None, base_url: str = "") -> ImgData | None:
#     width = int(tag.get('width',100)) if 
#     height = int(tag.get('height', 100))
#     if width < 50 or height < 50:
#         return None
#     if tag.get('role') == 'presentation' or tag.get('alt') == '':
#         return None
#     src = tag.get('src', '')
#     return ImgData(
#         src=src if src.startswith('http') else f"{base_url}{src}",
#         existingAlt=tag.get('alt'),
#         ariaLabel=tag.get('aria-label') or '',
#         ariaDescribedBy=get_aria_described_by(tag, soup),
#         parentContext=build_parent_context(page_title, tag),
#     )

# --- Top-level ---

def extract_visualizations(html_text: str, base_url: str = "") -> tuple[list[SvgData], list[ImgData]]:
    soup = BeautifulSoup(html_text, 'html.parser')
    page_title = get_page_title(soup)

    svgs = [extract_svg(tag, soup, page_title) for tag in soup.find_all('svg')]
    # imgs = [
    #     result for tag in soup.find_all('img')
    #     if (result := extract_img(tag, soup, page_title, base_url)) is not None
    # ]
    return svgs, []