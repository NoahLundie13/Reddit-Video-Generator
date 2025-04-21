from PIL import Image, ImageDraw, ImageFont

def make_title_box(text):
    image = Image.open("utils/reddit_frame.png")
    draw = ImageDraw.Draw(image)
    
    box_x, box_y = 20, 62  
    box_width, box_height = 445, 80  
    
    font_path = "utils/Montserrat-ExtraBold.ttf"
    max_font_size = 30  
    font_size = max_font_size
    
    while font_size > 10:
        font = ImageFont.truetype(font_path, font_size)
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            line_width, _ = draw.textbbox((0, 0), test_line, font=font)[2:4]
            if line_width <= box_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word  
        
        if current_line:
            lines.append(current_line)
        
        total_text_height = sum(draw.textbbox((0, 0), line, font=font)[3] for line in lines)
        
        if total_text_height <= box_height:
            break  
        
        font_size -= 2 
    
    text_y = box_y + (box_height - total_text_height) // 2
    for line in lines:
        draw.text((box_x, text_y), line, font=font, fill=(51, 51, 51))
        text_y += draw.textbbox((0, 0), line, font=font)[3]
    
    image.save("utils/output_image.png")
