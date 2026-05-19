#!/usr/bin/env python3
"""Generate EPUB from translated email articles.

Uses EbookLib to create a well-formatted EPUB file with:
- Table of contents
- Individual chapters per article
- Author and metadata
- CSS styling
"""

import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from ebooklib import epub


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    return text


def _clean_for_epub_id(text: str) -> str:
    """Create a valid EPUB ID from text."""
    # Remove non-alphanumeric chars, replace spaces with underscores
    cleaned = re.sub(r'[^\w\s-]', '', text)
    cleaned = re.sub(r'[\s-]+', '_', cleaned)
    return cleaned[:50] or 'article'


def generate_epub(
    translated_emails: List[Dict[str, Any]],
    schedule_label: str = "",
    output_dir: str = None
) -> str:
    """Generate an EPUB file from translated email articles.
    
    Args:
        translated_emails: List of translated email dicts
        schedule_label: Label for the schedule time slot
        output_dir: Output directory (default: epubs/YYYY-MM in project root)
    
    Returns:
        Path to the generated EPUB file
    """
    beijing_tz = timezone(timedelta(hours=8))
    now_beijing = datetime.now(beijing_tz)
    
    # Determine output directory: epubs/YYYY-MM/
    if output_dir is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        month_dir = now_beijing.strftime('%Y-%m')
        output_dir = os.path.join(project_root, 'epubs', month_dir)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename with date and time
    date_str = now_beijing.strftime('%Y-%m-%d')
    time_str = now_beijing.strftime('%H%M')
    filename = f"{date_str}_{time_str}.epub"
    filepath = os.path.join(output_dir, filename)
    
    # Create EPUB book
    book = epub.EpubBook()
    
    # Set metadata
    book.set_identifier(f"email-digest-{date_str}-{time_str}")
    title = f"邮件摘要 {date_str} {now_beijing.strftime('%H:%M')}"
    if schedule_label:
        title += f" ({schedule_label})"
    book.set_title(title)
    book.set_language('zh')
    book.add_author('Email Digest Bot')
    book.add_metadata('DC', 'description', f'每日邮件摘要 - {date_str}，共 {len(translated_emails)} 篇文章')
    book.add_metadata('DC', 'date', now_beijing.strftime('%Y-%m-%d'))
    
    # CSS styling
    style = '''
@namespace epub "http://www.idpf.org/2007/ops";
body {
    font-family: -apple-system, "Microsoft YaHei", "Noto Sans SC", Arial, sans-serif;
    line-height: 1.8;
    margin: 1em;
    color: #333;
}
h1 {
    font-size: 1.5em;
    color: #1a237e;
    border-bottom: 2px solid #1a237e;
    padding-bottom: 0.3em;
    margin-top: 1.5em;
}
h2 {
    font-size: 1.3em;
    color: #283593;
    border-bottom: 1px solid #ccc;
    padding-bottom: 0.2em;
    margin-top: 1.2em;
}
.meta {
    font-size: 0.85em;
    color: #666;
    margin-bottom: 1em;
}
.content {
    font-size: 1em;
    text-align: justify;
}
.content p {
    margin: 0.5em 0;
    text-indent: 2em;
}
.fail {
    color: #c0392b;
    font-style: italic;
}
.cover-page {
    text-align: center;
    padding: 3em 1em;
}
.cover-page h1 {
    font-size: 2em;
    border: none;
    color: #1a237e;
}
.cover-page .info {
    font-size: 1.1em;
    color: #555;
    margin-top: 1em;
}
'''
    
    nav_css = epub.EpubItem(
        uid='style_nav',
        file_name='style/nav.css',
        media_type='text/css',
        content=style
    )
    book.add_item(nav_css)
    
    # Create chapters
    chapters = []
    
    # Cover page / Introduction
    cover_content = f'''<html><body>
<div class="cover-page">
<h1>📰 邮件摘要</h1>
<div class="info">
<p>{_escape_html(date_str)} {now_beijing.strftime('%H:%M')} 北京时间</p>
<p>共 {len(translated_emails)} 篇文章</p>
{'<p>时段: ' + _escape_html(schedule_label) + '</p>' if schedule_label else ''}
</div>
</div>
</body></html>'''
    
    cover_chapter = epub.EpubHtml(
        title='封面',
        file_name='cover.xhtml',
        lang='zh'
    )
    cover_chapter.content = cover_content
    cover_chapter.add_item(nav_css)
    book.add_item(cover_chapter)
    
    # Article chapters
    for i, email in enumerate(translated_emails):
        # Get article title
        translated_subject = email.get('translated_subject') or email.get('original_subject', f'文章 {i+1}')
        original_subject = email.get('original_subject', '')
        author = email.get('author', '')
        
        # Clean title (remove sender prefix)
        cleaned_title = re.sub(r'^[^：:]+[：:]\s*', '', translated_subject).strip() or translated_subject
        
        # Build meta info
        meta_items = []
        if author:
            meta_items.append(f'作者: {_escape_html(author)}')
        
        original_time = email.get('original_time', '')
        if original_time:
            try:
                dt = datetime.fromisoformat(original_time.replace('Z', '+00:00'))
                beijing_time = dt.astimezone(beijing_tz).strftime('%Y-%m-%d %H:%M')
                meta_items.append(f'时间: {beijing_time}')
            except:
                pass
        
        eng_words = email.get('english_word_count', 0)
        ch_chars = email.get('chinese_char_count', 0)
        if eng_words > 0:
            meta_items.append(f'英文 {eng_words} 词 → 中文 {ch_chars} 字')
        
        models_used = email.get('models_used', email.get('model_used', ''))
        if models_used and models_used != 'none':
            if ',' in models_used:
                model_list = [m.strip() for m in models_used.split(',')]
                models_display = ' → '.join(model_list)
            else:
                models_display = models_used
            meta_items.append(f'模型: {_escape_html(models_display)}')
        
        # Build content
        translated_body = email.get('translated_body', '[无内容]')
        success = email.get('success', True)
        
        # Format paragraphs
        paragraphs = translated_body.split('\n\n')
        content_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            if para:
                content_paragraphs.append(f'<p>{_escape_html(para)}</p>')
        
        body_html = '\n'.join(content_paragraphs) if content_paragraphs else '<p>[无内容]</p>'
        
        if not success:
            body_html = f'<p class="fail">⚠️ 翻译失败</p>\n{body_html}'
        
        # Build chapter HTML
        chapter_html = f'''<html><body>
<h1>{_escape_html(cleaned_title)}</h1>
{'<h2>' + _escape_html(original_subject) + '</h2>' if original_subject and original_subject != cleaned_title else ''}
<div class="meta">{' | '.join(meta_items)}</div>
<div class="content">
{body_html}
</div>
</body></html>'''
        
        chapter_id = _clean_for_epub_id(cleaned_title) + f'_{i}'
        chapter_filename = f'chapter_{i+1}.xhtml'
        
        chapter = epub.EpubHtml(
            title=cleaned_title[:100],  # Truncate long titles for TOC
            file_name=chapter_filename,
            lang='zh',
            uid=chapter_id
        )
        chapter.content = chapter_html
        chapter.add_item(nav_css)
        book.add_item(chapter)
        chapters.append(chapter)
    
    # Table of contents
    book.toc = (
        [cover_chapter] + chapters
    )
    
    # Add navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Spine (reading order)
    book.spine = ['nav'] + [cover_chapter] + chapters
    
    # Write EPUB
    epub.write_epub(filepath, book, {})
    
    print(f"EPUB generated: {filepath} ({os.path.getsize(filepath)} bytes)")
    return filepath


if __name__ == "__main__":
    # Quick test
    test_emails = [
        {
            'translated_subject': '测试文章 - AI 技术突破',
            'original_subject': 'AI Technology Breakthrough',
            'translated_body': '这是一篇关于人工智能技术突破的测试文章。\n\n人工智能正在改变世界，最新的研究成果显示大语言模型的能力不断提升。\n\n研究人员表示，这项技术将在未来几年内带来深远影响。',
            'author': 'Test Author',
            'original_time': '2026-05-19T00:00:00Z',
            'success': True,
            'models_used': 'minimax-m2.7',
            'english_word_count': 150,
            'chinese_char_count': 80,
        },
        {
            'translated_subject': '测试文章 - 地缘政治分析',
            'original_subject': 'Geopolitical Analysis',
            'translated_body': '地缘政治格局正在发生变化。\n\n各国之间的关系不断调整，新的联盟正在形成。',
            'author': 'Another Author',
            'original_time': '2026-05-19T02:00:00Z',
            'success': True,
            'models_used': 'qwen3-coder',
            'english_word_count': 100,
            'chinese_char_count': 45,
        }
    ]
    
    path = generate_epub(test_emails, schedule_label="测试")
    print(f"Test EPUB: {path}")
