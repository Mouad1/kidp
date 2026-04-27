from PIL import ImageDraw, ImageFont

def draw_text_wrapped(draw, text: str, font, max_width: int, x: int, y: int, fill, line_spacing=1.3, align="left"):
    """Draws text wrapped within max_width. align: 'left' or 'center'"""
    lines = []
    paragraphs = text.split('\n')
    for p in paragraphs:
        if not p.strip():
            lines.append("")
            continue
        words = p.split()
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            # get length
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []
        if current_line:
            lines.append(" ".join(current_line))
    
    current_y = y
    
    # Use standard height for consistent line spacing
    bbox = draw.textbbox((0, 0), "Agy", font=font)
    h = (bbox[3] - bbox[1]) * line_spacing
    
    for line in lines:
        if line:
            w_bbox = draw.textbbox((0, 0), line, font=font)
            w = w_bbox[2] - w_bbox[0]
            
            draw_x = x
            if align == "center":
                draw_x = x + (max_width - w) // 2
                
            draw.text((draw_x, current_y), line, font=font, fill=fill)
            
        current_y += h
        
    return current_y - y # return total height drawn
