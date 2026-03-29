def create_cloze_cards(markdown_content, output_filename="cloze_cards.txt"):
    """
    将 Markdown 提取并转换为 Anki 完形填空格式。
    注意：导入 Anki 时，类型(Type) 必须选择 "Cloze" (完形填空)。
    """
    sections = markdown_content.split('### ')[1:]
    cloze_cards = []

    for section in sections:
        lines = section.strip().split('\n')
        if not lines:
            continue
        
        # 标题作为上下文提示
        title = lines[0].strip()
        
        # 提取所有公式
        formulas = re.findall(r'\$\$(.*?)\$\$', section, re.DOTALL)
        
        for formula in formulas:
            f_clean = formula.strip()
            # 核心逻辑：将整个公式放入完形填空 c1 中
            # 并在公式前后加上 MathJax 标记 \[ ... \]
            # 格式：标题 <br> {{c1::\[ 公式内容 \]}}
            card_text = f"{title}<br>{{{{c1::\\[ {f_clean} \\]}}}}"
            cloze_cards.append(card_text)

    with open(output_filename, 'w', encoding='utf-8') as f:
        # 完形填空通常只需要一个字段（Text）
        for card in cloze_cards:
            f.write(card + '\n')
            
    print(f"✅ 成功生成 {len(cloze_cards)} 张完形填空卡片！")


def extract_to_anki(markdown_content, output_filename="anki_cards.txt"):
    """
    解析 Markdown 内容并提取标题和公式，生成 Anki 可导入的 TSV 文件。
    """
    # 按 '### ' 分隔区块，跳过第一个（通常是前言或大标题）
    sections = markdown_content.split('### ')[1:]
    
    cards = []
    for section in sections:
        # 提取小标题作为正面 (Front)
        title_end_idx = section.find('\n')
        if title_end_idx == -1:
            continue
        
        front = section[:title_end_idx].strip()
        
        # 提取公式作为背面 (Back)
        # 匹配 $$ ... $$ 之间的所有内容，re.DOTALL 允许跨行匹配
        formulas = re.findall(r'\$\$(.*?)\$\$', section, re.DOTALL)
        
        if formulas:
            # Anki 默认支持 MathJax，推荐使用 \[ ... \] 表示独立块级公式
            # 如果一个标题下有多个公式，用 <br> (换行符) 连接
            formatted_formulas = [f"\\[ {f.strip()} \\]" for f in formulas]
            back = "<br>".join(formatted_formulas)
            
            cards.append([front, back])
    
    # 将提取的卡片数据写入 TSV (Tab-Separated Values) 文件
    with open(output_filename, 'w', encoding='utf-8', newline='') as f:
        # delimiter='\t' 指定使用 Tab 键分隔，这是 Anki 导入的最佳格式
        writer = csv.writer(f, delimiter='\t')
        writer.writerows(cards)
        
    print(f"✅ 成功提取了 {len(cards)} 张卡片，已保存到：{output_filename}")



def extract_to_reversed_anki(markdown_content, output_filename="anki_reversed_cards.txt"):
    """
    解析 Markdown 提取标题和公式，生成适合 'Basic (and reversed card)' 类型的 TSV 文件。
    """
    # 按 '### ' 分隔区块
    sections = markdown_content.split('### ')[1:]
    
    cards = []
    for section in sections:
        lines = section.strip().split('\n')
        if not lines:
            continue
            
        # 提取小标题作为正面 (Front)
        # 建议在标题中加入具体的提示，方便倒置卡片时更有上下文
        title = lines[0].strip()
        
        # 提取公式作为背面 (Back)
        formulas = re.findall(r'\$\$(.*?)\$\$', section, re.DOTALL)
        
        if formulas:
            # 使用 MathJax 格式
            formatted_formulas = [f"\\[ {f.strip()} \\]" for f in formulas]
            back = "<br>".join(formatted_formulas)
            
            # 字段1: 名称/描述, 字段2: 公式内容
            cards.append([title, back])
    
    # 写入 TSV
    with open(output_filename, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerows(cards)
        
    print(f"✅ 成功提取 {len(cards)} 组数据，已保存至：{output_filename}")

