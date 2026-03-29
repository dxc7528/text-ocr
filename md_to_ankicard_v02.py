import re
import csv
import os

# ==========================================
# 步骤 1: 核心制卡函数 (完全与 Markdown 解耦)
# ==========================================

def format_basic_card(concept, formula):
    """制作正反面卡片 (Basic)"""
    front = concept
    back = f"\\[ {formula} \\]"
    return [front, back]

def format_reversed_card(concept, formula):
    """
    制作基础及倒置卡片 (Basic and reversed)
    注意：数据结构与 Basic 完全一样，主要区别在于导出后的文件
    导入 Anki 时需手动选择 'Basic (and reversed card)' 类型
    """
    front = concept
    back = f"\\[ {formula} \\]"
    return [front, back]

def format_cloze_card(concept, formula, hide_target=None):
    """
    制作完形填空卡片 (Cloze)
    :param hide_target: 需要抠掉的具体变量，如果不传，则抠掉整个公式
    """
    if hide_target and hide_target in formula:
        # 抠掉特定的变量，保留公式其他部分
        cloze_formula = formula.replace(hide_target, f"{{{{c1::{hide_target}}}}}")
        text = f"{concept}<br>\\[ {cloze_formula} \\]"
    else:
        # 默认抠掉整个公式
        text = f"{concept}<br>{{{{c1::\\[ {formula} \\]}}}}"
    
    # 完形填空通常有两个字段：Text 和 Extra(备注，这里留空)
    return [text, ""]


# ==========================================
# 步骤 2: 模拟 AI 决策与调度器 (Router)
# ==========================================

def dispatch_card_creation(knowledge_item):
    """
    AI 调度器：根据 AI 传入的策略 (strategy) 调用不同的制卡函数
    """
    concept = knowledge_item.get("concept", "")
    formula = knowledge_item.get("formula", "")
    strategy = knowledge_item.get("strategy", "basic")
    hide_target = knowledge_item.get("hide_target", None)

    if strategy == "basic":
        return format_basic_card(concept, formula)
    elif strategy == "reversed":
        return format_reversed_card(concept, formula)
    elif strategy == "cloze":
        return format_cloze_card(concept, formula, hide_target)
    else:
        raise ValueError(f"未知的卡片策略: {strategy}")


# ==========================================
# 步骤 3: 文件导出与管理
# ==========================================

def save_to_tsv(cards, filename):
    """将卡片列表保存为 TSV 文件"""
    if not cards:
        return
        
    with open(filename, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerows(cards)
    print(f"✅ 成功保存 {len(cards)} 张卡片至：{filename}")


# ==========================================
# 测试演示：模拟 AI 处理后的结构化数据
# ==========================================

if __name__ == "__main__":
    # 假设这是 AI（例如 GPT/Gemini）阅读了你的 Markdown 后，
    # 自动提取、思考并结构化输出的 JSON/字典数据。
    # 这样就彻底摆脱了不稳定的 Markdown 正则匹配。
    
    ai_extracted_knowledge = [
        {
            "concept": "定額配当モデル（ゼロ成長モデル）の価格",
            "formula": "P_0 = \\frac{D}{k}",
            "strategy": "basic"  # AI 认为这个公式很简单，适合正反面
        },
        {
            "concept": "株主の要求収益率（株主資本コスト）… CAPM",
            "formula": "k = \\beta_i (E[R_M] - R_f) + R_f",
            "strategy": "reversed" # AI 认为这个需要双向记忆
        },
        {
            "concept": "定率成長モデルの価格",
            "formula": "P_0 = \\frac{D_1}{k - g}",
            "strategy": "cloze",
            "hide_target": "D_1" # AI 认为分子 "D1" 最容易记错，决定只抠掉 D1
        },
        {
            "concept": "サステイナブル成長率 g",
            "formula": "g = ROE \\times (1 - \\text{配当性向})",
            "strategy": "cloze",
            "hide_target": "(1 - \\text{配当性向})" # 抠掉内部留保率部分
        }
    ]

    # 初始化 3 个装载不同卡片类型的“篮子”
    card_baskets = {
        "basic": [],
        "reversed": [],
        "cloze": []
    }

    # 遍历知识点，分发制作卡片
    for item in ai_extracted_knowledge:
        card_data = dispatch_card_creation(item)
        strategy = item["strategy"]
        card_baskets[strategy].append(card_data)

    # 分别保存为 3 个不同的文件，方便 Anki 正确导入
    save_to_tsv(card_baskets["basic"], "export_basic.txt")
    save_to_tsv(card_baskets["reversed"], "export_reversed.txt")
    save_to_tsv(card_baskets["cloze"], "export_cloze.txt")