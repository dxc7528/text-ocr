# Markdown to Anki Flashcards Generator (Hybrid Architecture)

Markdown ファイル（とくに証券アナリスト等の金融・理数系のテキスト）に含まれる公式や解説文から、高品質な Anki 穴埋めカード（Cloze deletion）を自動生成するツールです。

## プロジェクトの背景と目的

従来、LLMのみを使用して数式の穴埋めカードを生成しようとすると、以下のような課題がありました：
1. **Hint（ヒント）が答えを漏洩してしまう**（例：`{{c1::k::割引率}}` とすると「割引率」自体が答えになってしまう）
2. **1つの公式に対して複数の変数を個別にテストするための `c1, c2, c3` の割り当てが不安定**
3. 穴埋め問題に説明文が混ざってしまい、**厳密な LaTeX 形式が保持されない**（文章と数式が混在したハイブリッドなカードになってしまう）
4. LLMの出力結果がプロンプトの調整だけでは完全にコントロールしきれない

そこで本プロジェクトでは、**[Pythonスクリプト (確実な数式解析)] + [LLM (高度な意味解析)]** のハイブリッドアーキテクチャを採用することで、上記の問題を根本から解決しました。

### 主要な機能・達成したこと

1. **Formula（数式）カードの確実な生成 (Python)**
   * 正規表現と構文解析により、等号（`=`）の右辺にある変数を正確に抽出し、確実に各変数へ個別のクロージャ番号（`c1, c2, c3...`）を付与（Multi-cloze）します。
   * Hintを出力しない設計にし、答えの漏洩を完全に防止しています。
   * LaTeX（`$$` や `$`）のフォーマットを崩しません。

2. **Text（テキスト）カードのスマートな抽出 (Gemini API)**
   * 「解説」や「留意点」のテキストセクションを LLM に渡し、「定義 (Definition)」「因果関係 (Causality)」「対比 (Contrast)」「並列 (Parallel)」「順序 (Sequential)」などのカードを自動生成します。

3. **自動バリデーションと修正 (Python)**
   * 万が一LLMが誤ってHintを出力したり、問題文の外側（括弧内など）に答えのヒントを含めてしまったりした場合でも、後処理（Validator）で自動的に検知し、安全な形に修正・除去します。

## アーキテクチャ

```
入力 Markdown ファイル (.md)
  ↓
Stage 1: Parser (Python)
  入力ファイルを「Point」「解説」「留意点」の3セクションに構造化して分割
  ↓
  ├─ Stage 2A: Formula Processor (Python)
  │    Pointセクション内の数式から、ヒントなしの確定的なルールで穴埋めカードを生成
  │
  └─ Stage 2B: Text Processor (Gemini API / LLM)
       「解説」「留意点」などのテキストから、意味を理解して概念カードを生成
  ↓
Stage 3: Validator (Python)
  ルール違反（Hintの漏れ、Anti-hint違反、一カード一項目原則など）のチェックと自動修正
  ↓
Stage 4: TSV Export
  Anki に直接インポート可能な形式（TSV）でのファイル出力
```

## インストールと準備

本プロジェクトはパッケージマネージャ `uv` を使用して管理されています。

### 1. 依存関係のインストール

以下のコマンドで依存関係をインストールします。

```bash
uv sync
```

### 2. 環境変数の設定

LLM（Google Gemini API）を使用するために、`.env` ファイルを作成してAPIキーを設定してください。

```bash
# .env.example を元に .env を作成
cp .env.example .env
```
`.env` ファイル内を編集し、ご自身のAPIキーを記載します：
```
GEMINI_API_KEY=your_api_key_here
```

## 使用方法

### 特定のファイルを処理する

単一のファイルを指定して実行します。

```bash
uv run python anki_generator.py "input/markdown_output/配当割引モデル.md" output/
```

### 複数のファイルを一括処理する

入力ディレクトリを指定することで、ディレクトリ内のすべての `.md` ファイルを処理できます。

```bash
uv run python anki_generator.py "input/markdown_output/" output/
```

### LLMを使わず、数式（Formula）カードのみを高速生成する

テキストの概念カードが不要な場合や、APIを使用したくない場合は `--no-llm` オプションを指定します。Pythonベースの数式処理・穴埋めカード生成のみが実行されます。

```bash
uv run python anki_generator.py "input/markdown_output/" output/ --no-llm
```

## 出力ファイルと Anki へのインポート

プログラムを実行すると、指定した出力ディレクトリ（上記例では `output/` またはデフォルト）に `{ファイル名}_cloze.tsv` という形式で TSV ファイルが生成されます。

このファイルを Anki にインポートする際は、以下の設定を行ってください：
* 出力形式は `Tab` 区切りです
* ノートタイプ（Note Type）を「**穴埋め (Cloze)**」に設定して読み込んでください
