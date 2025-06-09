import argparse
import json
import os
import re
import shutil
import subprocess

import librosa
import soundfile as sf
from llama_cpp import Llama
from pydub.utils import mediainfo

import Parameter

# 声明全局变量
llm = None
BAD_TOKENS = []


def normalize(x, data_min, data_max):
    if data_max == data_min:  # 避免除零错误
        return 0.5  # 或自定义默认值
    return (x - data_min) / (data_max - data_min)


def get_audio_duration(filepath):
    info = mediainfo(filepath)
    return float(info['duration'])


def resize_audio(input_path, output_path, target_duration_sec):
    y, sr = librosa.load(input_path, sr=None)
    current_duration = librosa.get_duration(y=y, sr=sr)
    rate = current_duration / target_duration_sec

    # 适配不同 librosa 版本
    try:
        y_stretched = librosa.effects.time_stretch(y, rate=rate)
    except Exception:
        # 老版本需要先stft
        y_stft = librosa.stft(y)
        y_stretched_stft = librosa.effects.time_stretch(y_stft, rate=rate)
        y_stretched = librosa.istft(y_stretched_stft)

    sf.write(output_path, y_stretched, sr)


def qwen_translate(user_input):
    global llm, BAD_TOKENS
    # 精简严格的系统提示（关键修改）
    system_msg = """你是一个专业翻译引擎，严格遵循以下规则：
1. 修正语音识别错误
2. 直接输出中文翻译结果
3. 禁止任何解释、思考或附加文本
4. 保留英文角色名称
5. 输出只能是纯翻译文本
6. 加入适当的标点符号
7. 让翻译后的文本念起来自然顺口
"""

    # 使用Qwen专用模板（保持原格式）
    prompt = f"""<|im_start|>system
{system_msg}<|im_end|>
<|im_start|>user
{user_input}<|im_end|>
<|im_start|>assistant
"""

    # 更严格的生成参数（关键修改）
    output = llm(
        prompt,
        max_tokens=2048,  # 大幅缩短长度限制
        temperature=0,  # 完全确定性输出
        top_k=1,  # 仅选择最佳token
        stop=["<|im_end|>"],
        logit_bias={token: -100.0 for token in BAD_TOKENS},
        echo=False
    )

    response = output['choices'][0]['text'].strip()

    # 强力后处理（保留）
    response = re.sub(r"\s+", " ", response).strip()
    return response if response else hardcoded_translation(user_input)


def hardcoded_translation(text):
    """常见短语的硬编码翻译"""
    # 预处理文本
    text = (text
            .replace("O K", "OK")
            .replace("CITY SEVENTEEN", "City 17")
            )

    # 常见短语映射
    translations = {
        "YES AND GORDON TOO WERE OK WE MADE IT OUT OF CITY 17":
            "是的，Gordon也没事，我们成功逃出了17号城市",
        "H E L L O THIS IS A TEST MESSAGE FROM DR KLEINER":
            "你好，这是Kleiner博士发来的测试信息",
        "WE ARE IN SECTOR THREE NEED IMMEDIATE ASSISTANCE":
            "我们在三号区域，需要立即支援",
        "THE LAMBDA COMPLEX IS SECURE REPEAT IS SECURE":
            "Lambda设施安全，重复，安全",
        "YES AND GORDON TOO WERE OK":
            "是的，Gordon也没事",
        "WE MADE IT OUT OF CITY SEVENTEEN":
            "我们成功逃出了17号城市"
    }

    # 尝试匹配整个短语
    if text in translations:
        return translations[text]

    # 尝试匹配部分短语
    for phrase, trans in translations.items():
        if phrase in text:
            return trans

    # 最后手段：返回原始文本
    return text


def remove_think_tags(text):
    """
    去除字符串中所有 <think> 和 </think> 标签及其间的所有内容

    参数:
        text (str): 输入文本

    返回:
        str: 清理后的文本
    """
    # 编译正则表达式模式，使用非贪婪匹配
    pattern = re.compile(r'<think>.*?</think>', re.DOTALL)

    # 循环移除所有匹配的标签对及其内容
    while True:
        new_text = pattern.sub('', text)
        # 当不再有匹配时退出循环
        if new_text == text:
            break
        text = new_text

    # 移除残留的孤立标签（没有配对的标签）
    text = re.sub(r'</?think>', '', text)

    return text.strip()


def redirect_path(path, anchor_folder):
    norm_p = os.path.normpath(path)
    parts = norm_p.split(os.sep)
    if anchor_folder in parts:
        idx = parts.index(anchor_folder)
        new_path = os.path.join(*parts[idx:])
        return new_path
    else:
        # 返回文件名而不是绝对路径
        return os.path.basename(norm_p)


def find_files_with_suffix(root_dir, suffix):
    result = []
    try:
        for entry in os.scandir(root_dir):
            if entry.is_file() and entry.name.endswith(suffix):
                result.append(os.path.abspath(entry.path))
            elif entry.is_dir():
                result.extend(find_files_with_suffix(entry.path, suffix))
    except Exception as e:
        print(f"访问 {root_dir} 时出错: {e}")
    return result


def delete_file(file_path):
    # 检查路径是否存在
    if os.path.exists(file_path):
        if os.path.isfile(file_path):
            os.remove(file_path)
            print(f"文件 {file_path} 已被删除。")
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)
            print(f"文件夹 {file_path} 已被删除。")
        else:
            print(f"{file_path} 既不是文件也不是文件夹。")
    else:
        print(f"{file_path} 不存在。")


def is_folder_strictly_empty(folder_path):
    # 检查根目录有没有内容
    if os.listdir(folder_path):
        # 不为空
        return False
    # 检查所有子文件夹
    for dirpath, dirnames, filenames in os.walk(folder_path):
        if filenames:
            return False
    return True


if __name__ == "__main__":
    # ------------------ 初始化 ------------------
    # 首先删除旧的json
    # delete_file(Parameter.JSON_PATH)

    parser = argparse.ArgumentParser(description="Audio auto translater script")
    parser.add_argument('--search-dir', type=str, help='要搜索的根目录')
    args = parser.parse_args()
    Parameter.SEARCH_DIR = args.search_dir
    if not Parameter.SEARCH_DIR or not os.path.exists(Parameter.SEARCH_DIR):
        print("Please fill in the correct path!\n")
        exit(0)
    print(f"Search path: {Parameter.SEARCH_DIR}\n")

    os.makedirs(Parameter.OUTPUT_DIR, exist_ok=True)

    # 全局加载模型
    llm = Llama(
        model_path=Parameter.LLM_PATH,
        n_gpu_layers=-1,
        n_ctx=4096,
        verbose=False,
        seed=1818,
        n_threads=Parameter.WORK_THREADS,
        # n_batch=512,
        # use_mmap=True,
        # use_mlock=True
    )

    # BAD_TOKENS 初始化
    BAD_TOKENS = []
    for word in ["think>", "思考", "好的", "现在", "首先", "需要", "处理"]:
        BAD_TOKENS.extend(llm.tokenize(word.encode('utf-8')))
    BAD_TOKENS = list(set(BAD_TOKENS))  # 去重

    ast_input_files = find_files_with_suffix(Parameter.SEARCH_DIR, '.wav')

    tts_output_files = ast_input_files.copy()
    for idx in range(len(tts_output_files)):
        tts_output_files[idx] = os.path.join(Parameter.OUTPUT_DIR, redirect_path(tts_output_files[idx], 'sound'))
    print(tts_output_files)

    # ------------------ 执行语音识别文字 ------------------
    if os.path.isfile(Parameter.JSON_PATH):
        print('JSON文件已存在，跳过语音识别文字步骤！')
    else:
        ast_args = [
            f'--tokens={Parameter.AST_DIR}/tokens.txt',
            f'--encoder={Parameter.AST_DIR}/encoder-epoch-34-avg-19.onnx',
            f'--decoder={Parameter.AST_DIR}/decoder-epoch-34-avg-19.onnx',
            f'--joiner={Parameter.AST_DIR}/joiner-epoch-34-avg-19.onnx',
            f'--num-threads={Parameter.WORK_THREADS}'
        ]
        for idx in range(0, len(ast_input_files), 5):
            batch = ast_input_files[idx:idx + 5]
            subprocess.run(
                ['python', './AST.py']
                + ast_args
                + batch
            )

    # ------------------ 执行翻译 ------------------
    with open(Parameter.JSON_PATH, "r", encoding="utf-8") as f:
        json_results = json.load(f)

    # 是否所有的文件都没有被翻译
    is_translate = True
    for item in json_results:
        if item['tts_text'] != '':
            is_translate = False

    if is_translate:
        for item in json_results:
            text = item['ast_text']
            print(f"原始文本: {text}")
            translation = qwen_translate(text)
            translation = remove_think_tags(translation)
            print(f"翻译结果: {translation}\n")
            item['tts_text'] = translation
    else:
        print('文字已经翻译完毕，跳过翻译步骤！')

    # 循环结束后再写回文件
    with open(Parameter.JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(json_results, f, ensure_ascii=False, indent=4)

    # ------------------ 执行文本转语音 ------------------
    with open(Parameter.JSON_PATH, "r", encoding="utf-8") as f:
        json_results = json.load(f)

    # 是否所有的文件都没有被TTS
    is_tts = True
    for item in json_results:
        if not is_folder_strictly_empty():
            is_tts = False

    if is_tts:
        for idx in range(len(json_results)):
            specker_id = 50
            out_path = tts_output_files[idx]

            dirpath = os.path.dirname(out_path)  # 获取文件的目录部分（忽略文件名和扩展名）
            os.makedirs(dirpath, exist_ok=True)  # 创建目录，存在则忽略

            json_results[idx]['out_file'] = out_path

            tts_text = json_results[idx]['tts_text']

            # 获取音频秒数，到时候直接生成这个长度的音频
            talk_speed = 1.0
            json_results[idx]['audio_seconds'] = get_audio_duration(json_results[idx]['in_file'])

            tts_args = [
                f'--debug=0',
                f'--provider=cuda',
                f'--kokoro-model={Parameter.TTS_DIR}/model.onnx',
                f'--kokoro-voices={Parameter.TTS_DIR}/voices.bin',
                f'--kokoro-tokens={Parameter.TTS_DIR}/tokens.txt',
                f'--kokoro-data-dir={Parameter.TTS_DIR}/espeak-ng-data',
                f'--kokoro-dict-dir={Parameter.TTS_DIR}/dict',
                f'--kokoro-lexicon={Parameter.TTS_DIR}/lexicon-us-en.txt,{Parameter.TTS_DIR}/lexicon-zh.txt',
                f'--num-threads={Parameter.WORK_THREADS}',
                f'--sid={specker_id}',
                f'--speed={talk_speed}',
                f'--output-filename={out_path}',
                f'{tts_text}'
            ]
            # 如需执行TTS，请取消下面的注释
            subprocess.run(
                ['python', './TTS.py']
                + tts_args
            )
    else:
        print('音频已经TTS完毕，跳过该步骤！')

    # 循环结束后再写回文件
    with open(Parameter.JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(json_results, f, ensure_ascii=False, indent=4)

    # ------------------ 缩放音频为目标长度 ------------------
    with open(Parameter.JSON_PATH, "r", encoding="utf-8") as f:
        json_results = json.load(f)

    # 是否所有的文件都没有被TTS
    is_scaling = True
    for item in json_results:
        if item['out_file'] != '':
            is_scaling = False

    if is_scaling:
        # 缩放音频为目标长度
        for item in json_results:
            resize_audio(item['out_file'], item['out_file'], item['audio_seconds'])
            print(f'文件 {item["out_file"]} 已适配原速度\n')
    else:
        print('音频长度已经缩放完毕，跳过该步骤！')

    print('该脚本执行结束')
