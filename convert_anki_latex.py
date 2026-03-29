import re
import sys

def fix_cma_fatal_errors(text: str) -> str:
    """
    前置数据清洗：自动修复 OCR 识别错误和会导致 MathJax 渲染崩溃的物理结构断裂。
    """
    # 1. 修复错误的求和符号上下标拆分: \su{{c2::m_{j=1}}}^{{{c3::k}}} -> \sum_{j=1}^{k}
    text = re.sub(
        r'\\su\{\{c\d+::m_\{([^}]+)\}\}\}\^\{\{\{c\d+::([^}]+)\}\}\}',
        r'\\sum_{\1}^{\2}',
        text
    )
    
    # 2. 修复孤立的 \su 拼写错误
    text = text.replace(r'\su', r'\sum')
    
    # 3. 强制剥离 \text{} 和 \mathrm{}，防止内部的挖空标签切断外部大括号导致渲染崩溃
    text = re.sub(r'\\text\{\s*(\{\{c\d+::.*?\}\})\s*\}', r'\1', text)
    text = re.sub(r'\\mathrm\{\s*(\{\{c\d+::.*?\}\})\s*\}', r'\1', text)
    
    return text

def merge_adjacent_clozes(text: str) -> str:
    """
    合并相邻挖空：将紧密的乘积项等相邻挖空合并为一个整体。
    例如：{{c2::b_{i1}}}{{c3::\lambda_1}} -> {{c2::b_{i1}\lambda_1}}
    包含中间可能有空格的情况：{{c2::A}} {{c3::B}} -> {{c2::A B}}
    """
    pattern = re.compile(r'\{\{c(\d+)::(.*?)\}\}(\s*)\{\{c\d+::(.*?)\}\}')
    while True:
        new_text = pattern.sub(r'{{c\1::\2\3\4}}', text)
        if new_text == text:
            break
        text = new_text
    return text

def flatten_latex_fractions(latex_str: str) -> str:
    """
    降维展平：将包含挖空的 \frac{A}{B} 强制转换为线性的 (A) / (B)。
    """
    while r'\frac{' in latex_str:
        start_idx = latex_str.find(r'\frac{')
        
        # 提取分子
        num_start = start_idx + 6
        brace_count = 1
        num_end = num_start
        while num_end < len(latex_str) and brace_count > 0:
            if latex_str[num_end] == '{': brace_count += 1
            elif latex_str[num_end] == '}': brace_count -= 1
            num_end += 1
        numerator = latex_str[num_start:num_end-1]
        
        # 提取分母
        den_start = latex_str.find('{', num_end - 1) + 1
        brace_count = 1
        den_end = den_start
        while den_end < len(latex_str) and brace_count > 0:
            if latex_str[den_end] == '{': brace_count += 1
            elif latex_str[den_end] == '}': brace_count -= 1
            den_end += 1
        denominator = latex_str[den_start:den_end-1]
        
        # 替换为线性结构
        replacement = f" ( {numerator} ) / ( {denominator} ) "
        latex_str = latex_str[:start_idx] + replacement + latex_str[den_end:]
        
    return latex_str

def fragment_mathjax(latex_str: str) -> str:
    """
    碎片化隔离：将公式切片，确保 {{c...}} 永远处于数学环境 \( ... \) 外部。
    """
    parts = re.split(r'(\{\{c\d+::.*?\}\})', latex_str)
    result = []
    
    for part in parts:
        if not part:
            continue
            
        if part.startswith('{{c'):
            match = re.match(r'(\{\{c\d+::)(.*?)(\}\})', part)
            if match:
                prefix, content, suffix = match.groups()
                # 剔除挖空内容中可能残留的 $ 符号，防止嵌套错误
                content_clean = content.strip().replace('$', '')
                result.append(f"{prefix}\\({content_clean}\\){suffix}")
        else:
            stripped = part.strip()
            if stripped:
                result.append(f"\\({stripped}\\)")
                
    return " ".join(result)

def process_line(line: str) -> str:
    # 1. 全局前置清洗
    line = fix_cma_fatal_errors(line)
    
    # 2. 合并相邻挖空
    line = merge_adjacent_clozes(line)
    
    # 3. 处理块级公式 $$...$$
    def replace_block(match):
        content = match.group(1)
        if '{{c' in content:
            content = flatten_latex_fractions(content)
            return fragment_mathjax(content)
        return f"\\({content}\\)"
        
    line = re.sub(r'\$\$(.*?)\$\$', replace_block, line)
    
    # 3. 处理行内公式 $...$
    def replace_inline(match):
        content = match.group(1)
        if '{{c' in content:
            content = flatten_latex_fractions(content)
            return fragment_mathjax(content)
        return f"\\({content}\\)"
        
    line = re.sub(r'\$(.*?)\$', replace_inline, line)
    
    return line

def main():
    if len(sys.argv) < 3:
        print("Usage: python convert_anki_latex.py <input.tsv> <output.tsv>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    with open(input_file, 'r', encoding='utf-8') as fin, \
         open(output_file, 'w', encoding='utf-8') as fout:
        for line in fin:
            fout.write(process_line(line))
            
    print(f"✅ Conversion complete: {output_file}")

if __name__ == "__main__":
    main()