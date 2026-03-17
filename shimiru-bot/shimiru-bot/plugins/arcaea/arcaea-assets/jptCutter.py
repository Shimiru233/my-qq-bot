from PIL import Image
import random

def random_crop_quarter(input_path, output_path):
    # 打开图片
    img = Image.open(input_path)
    width, height = img.size

    # 裁剪尺寸 = 原图的 1/4
    crop_w = width // 2
    crop_h = height // 2

    # 随机左上角
    x = random.randint(0, width - crop_w)
    y = random.randint(0, height - crop_h)

    # 裁剪区域
    crop_box = (x, y, x + crop_w, y + crop_h)

    cropped = img.crop(crop_box)

    # 保存
    cropped.save(output_path, "JPEG")

# 示例
random_crop_quarter("input.jpg", "output.jpg")
