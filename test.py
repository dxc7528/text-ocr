import os
from PIL import Image
import pillow_heif
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions, CodeFormulaVlmOptions
from docling.datamodel.base_models import InputFormat
from docling.document_converter import ImageFormatOption

def process_heic_to_markdown(heic_file_path: str, output_md_path: str):
    """
    将 HEIC 图片中的日语文本和公式提取为 Markdown (LaTeX)
    """
    temp_png_path = "temp_converted_image.png"

    try:
        # ==========================================
        # 1. 预处理：将 HEIC 转换为 PNG
        # ==========================================
        print(f"正在读取 HEIC 文件: {heic_file_path}")
        # 读取 HEIC 文件
        heif_file = pillow_heif.read_heif(heic_file_path)
        # 转换为 PIL Image 对象
        image = Image.frombytes(
            heif_file.mode,
            heif_file.size,
            heif_file.data,
            "raw",
        )
        # 保存为 Docling 原生支持的 PNG 格式
        image.save(f"tmp/{temp_png_path}", format="png")
        print("已成功将 HEIC 转换为临时 PNG 文件。")

        # ==========================================
        # 2. 配置 Docling (日语 OCR + 公式识别)
        # ==========================================
        print("正在初始化 Docling 并配置 OCR 引擎...")

        # 配置 Pipeline 参数
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True  # 强制启用 OCR
        pipeline_options.do_formula_enrichment = True  # 启用公式识别

        # 配置公式识别使用 codeformulav2 preset
        pipeline_options.code_formula_options = CodeFormulaVlmOptions.from_preset("codeformulav2")

        # 配置 EasyOCR 处理日语 ("ja") 和英语 ("en")
        pipeline_options.ocr_options = EasyOcrOptions(lang=["ja", "en"], force_full_page_ocr=True)

        # 初始化 DocumentConverter，并将配置应用到图像格式处理中
        converter = DocumentConverter(
            format_options={
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options)
            }
        )

        # ==========================================
        # 3. 执行提取与转换
        # ==========================================
        print("正在提取图片内容（文本与公式）...")
        result = converter.convert(f"tmp/{temp_png_path}")

        # 导出为 Markdown 格式（内置自动包含格式化的 LaTeX 公式）
        markdown_content = result.document.export_to_markdown()

        # ==========================================
        # 4. 保存为 Markdown 文件
        # ==========================================
        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
            
        print(f"✅ 提取成功！Markdown 文件已保存至: {output_md_path}")

    except Exception as e:
        print(f"❌ 处理过程中发生错误: {e}")
        
    finally:
        pass

if __name__ == "__main__":
    # 使用示例：将此处替换为你的实际文件路径
    INPUT_HEIC = "input/IMG_5701.heic"  # 输入的 HEIC 文件
    OUTPUT_MD = "output/IMG_5701.md"  # 输出的 Markdown 文件

    # 请确保输入文件存在后再运行
    if os.path.exists(INPUT_HEIC):
        process_heic_to_markdown(INPUT_HEIC, OUTPUT_MD)
    else:
        print(f"找不到输入文件: {INPUT_HEIC}，请检查路径。")