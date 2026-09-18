#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为StudyBuddy所有HTML页面的交互元素添加title属性
提供按钮操作顺序引导
"""
import re
import sys
from pathlib import Path

# 设置stdout为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 定义每个页面的按钮title映射
BUTTON_TITLES = {
    'materials.html': {
        'folder-btn': '[1] 导入文件夹 - 批量导入整个文件夹中的所有文件',
        'apply-filters': '[2] 应用筛选 - 按状态筛选材料（成功、空文件、失败等）',
        'view-deleted': '[3] 查看回收站 - 查看已删除的材料，可以恢复',
        'search': '[4] 搜索材料 - 输入关键词搜索材料名称或内容',
    },
    'material-detail.html': {
        'qa': '[1] 进入问答 - 对这个材料提问（需先建立索引）',
        'index': '[2] 建立AI索引 - 让AI可以理解材料内容',
        'queue-index': '[3] 加入索引任务 - 将索引任务加入后台队列',
        'export-original': '[4] 下载原文件 - 下载上传时的原始文件',
        'export-text': '[5] 导出解析文本 - 导出解析出的纯文本',
        'refresh-page': '[6] 刷新状态 - 重新加载材料详情',
        'refresh-candidates': '[7] 刷新来源候选 - 重新加载来源候选列表',
        'link-add': '[8] 关联到学习项 - 将选中的材料片段关联到学习计划',
    },
    'qa.html': {
        'index-btn': '[1] 建立索引 - 必须先执行，让AI可以理解材料内容',
        'qa-question': '[2] 输入问题 - 输入与材料相关的问题',
        'submit-btn': '[3] 提问 - 发送问题给AI，查看答案和引用来源',
        'new-thread-btn': '[4] 新建对话 - 开始一个新的问答对话',
    },
    'tasks.html': {
        'apply-filters': '[1] 应用筛选 - 按任务类型和状态筛选',
        'refresh-btn': '[2] 刷新 - 重新加载任务列表',
    },
    'cards.html': {
        'refresh-decks': '[1] 刷新 - 重新加载卡片组列表',
        'deck-title': '[2] 卡片组标题 - 输入新卡片组的标题',
        'deck-source-material': '[3] 来源材料 - 选择要从哪个材料生成卡片',
    },
    'exercises.html': {
        'refresh-sets': '[1] 刷新列表 - 重新加载练习集',
        'set-title': '[2] 练习集标题 - 输入新练习集的标题',
    },
    'plans.html': {
        'plan-goal-title': '[1] 目标名称 - 输入学习目标，例如"期末考试90分"',
        'plan-module-title': '[2] 模块名称 - 输入学习模块，例如"五年级语文上册"',
        'plan-title': '[3] 计划标题 - 输入学习计划的标题',
        'source-refresh': '[4] 刷新来源 - 重新加载可用的材料和模块',
        'refresh-all': '[5] 刷新数据 - 重新加载所有目标、模块和计划',
    },
    'plan-detail.html': {
        'refresh-progress': '[1] 刷新进度 - 重新计算学习进度',
    },
    'notes.html': {
        'note-title': '[1] 笔记标题 - 输入笔记标题',
        'note-module': '[2] 关联模块 - 选择要关联的学习模块',
        'reload-materials': '[3] 重新加载材料列表 - 刷新可选的材料',
        'generate': '[4] 生成AI草稿 - 让AI生成笔记内容草稿（需确认）',
        'refresh': '[5] 刷新列表 - 重新加载笔记列表',
        'refresh-notes': '[6] 刷新笔记 - 重新加载笔记内容',
        'link-module': '[7] 关联到当前笔记 - 将材料关联到选中的笔记',
    },
    'practice.html': {
        'refresh-cram': '[1] 刷新冲刺 - 重新加载冲刺目标',
        'cram-goal-title': '[2] 冲刺目标 - 输入期末冲刺目标',
        'create-cram-goal': '[3] 创建冲刺目标 - 开始新的期末冲刺计划',
        'refresh-recommendations': '[4] 刷新推荐 - 重新获取练习推荐',
    },
    'capture.html': {
        'new-session-btn': '[1] 新建采集会话 - 开始课堂音频/图片采集',
        'refresh-btn': '[2] 刷新 - 重新加载采集会话列表',
    },
    'classroom.html': {
        'refresh-captures': '[1] 刷新采集列表 - 重新加载当前会话的采集记录',
        'confirm-transcript': '[2] 确认转写 - 确认AI转写的文本（可以先编辑）',
    },
    'reports.html': {
        'report-create-submit': '[1] 生成报告 - 根据选择的时间范围生成学习报告',
    },
    'settings.html': {
        'capability-recheck': '[1] 重新自检 - 重新检测所有组件能力状态',
        'capability-refresh': '[2] 刷新状态 - 刷新能力状态显示',
        'ai-save': '[3] 保存AI配置 - 保存并生效Chat模型配置',
        'ai-clear': '[4] 清除AI配置 - 清除已保存的Chat配置',
        'embedding-save': '[5] 保存Embedding配置 - 保存并生效Embedding模型配置',
        'embedding-clear': '[6] 清除Embedding配置 - 清除已保存的Embedding配置',
        'local-save': '[7] 保存本机组件 - 保存并生效本机OCR/ASR配置',
        'local-clear': '[8] 清除本机组件 - 清除本机组件配置覆盖',
    },
    'settings-provider.html': {
        'provider-copy': '[1] 复制Provider环境变量 - 复制到剪贴板（仅内存生成）',
        'provider-test': '[2] 测试Provider连接 - 测试与AI服务的连接',
        'email-copy': '[3] 复制Email环境变量 - 复制到剪贴板（仅内存生成）',
        'email-test': '[4] 测试Email连接 - 测试SMTP邮件发送',
    },
    'note-detail.html': {
        'retry-note': '[1] 重新加载 - 刷新笔记详情页面',
    },
    'practice-result.html': {
        'retry-result': '[1] 重新加载 - 刷新练习结果页面',
    },
    'practice-session.html': {
        'retry-session': '[1] 重新加载 - 刷新答题会话页面',
    },
    'review.html': {
        'retry-review': '[1] 重新加载 - 刷新错题复习页面',
        'load-more-review': '[2] 加载更多 - 加载更多错题记录',
        'retry-weak-points': '[3] 重新加载弱点 - 刷新薄弱知识点分析',
    },
    'today.html': {
        'retry-today': '[1] 重新加载 - 刷新今日学习页面',
    },
    'rhythm.html': {
        # 该页面可能没有交互按钮
    },
}


def add_title_to_button(html_content: str, button_id: str, title: str) -> str:
    """为指定ID的按钮添加title属性"""
    # 匹配按钮标签，支持多行和已有title
    pattern = rf'(<button[^>]*\bid\s*=\s*["\']?{re.escape(button_id)}["\']?[^>]*)(>)'
    
    def replace_func(match):
        opening_tag = match.group(1)
        closing = match.group(2)
        
        # 如果已有title，替换它
        if 'title=' in opening_tag:
            opening_tag = re.sub(
                r'title\s*=\s*["\'][^"\']*["\']',
                f'title="{title}"',
                opening_tag
            )
        else:
            # 没有title，添加
            opening_tag = opening_tag + f' title="{title}"'
        
        return opening_tag + closing
    
    return re.sub(pattern, replace_func, html_content, flags=re.IGNORECASE)


def add_title_to_input(html_content: str, input_id: str, title: str) -> str:
    """为指定ID的输入框添加title属性"""
    pattern = rf'(<(?:input|textarea|select)[^>]*\bid\s*=\s*["\']?{re.escape(input_id)}["\']?[^>]*)(/?)(>)'
    
    def replace_func(match):
        opening_tag = match.group(1)
        self_close = match.group(2)
        closing = match.group(3)
        
        if 'title=' in opening_tag:
            opening_tag = re.sub(
                r'title\s*=\s*["\'][^"\']*["\']',
                f'title="{title}"',
                opening_tag
            )
        else:
            opening_tag = opening_tag + f' title="{title}"'
        
        return opening_tag + self_close + closing
    
    return re.sub(pattern, replace_func, html_content, flags=re.IGNORECASE)


def process_html_file(file_path: Path) -> bool:
    """处理单个HTML文件，添加title属性"""
    filename = file_path.name
    
    if filename not in BUTTON_TITLES:
        print(f"  ⚠ 跳过 {filename} - 没有配置title映射")
        return False
    
    # 读取文件
    content = file_path.read_text(encoding='utf-8')
    original_content = content
    
    # 应用所有title
    titles = BUTTON_TITLES[filename]
    modified = False
    
    for element_id, title in titles.items():
        new_content = add_title_to_button(content, element_id, title)
        if new_content != content:
            modified = True
            print(f"    ✓ 添加 button#{element_id}")
            content = new_content
            continue
        
        # 尝试作为input处理
        new_content = add_title_to_input(content, element_id, title)
        if new_content != content:
            modified = True
            print(f"    ✓ 添加 input#{element_id}")
            content = new_content
    
    # 写回文件
    if modified:
        file_path.write_text(content, encoding='utf-8')
        print(f"  ✓ 已更新 {filename}")
        return True
    else:
        print(f"  ℹ {filename} 没有匹配的元素")
        return False


def main():
    """主函数"""
    templates_dir = Path('H:/studybuddy/backend/app/static')
    
    if not templates_dir.exists():
        print(f"错误：模板目录不存在: {templates_dir}")
        return 1
    
    print(f"正在处理 {templates_dir} 下的HTML文件...\n")
    
    html_files = sorted(templates_dir.glob('*.html'))
    processed = 0
    modified = 0
    
    for html_file in html_files:
        print(f"处理 {html_file.name}:")
        if process_html_file(html_file):
            modified += 1
        processed += 1
        print()
    
    print(f"\n完成！")
    print(f"  处理文件: {processed}")
    print(f"  修改文件: {modified}")
    print(f"  跳过文件: {processed - modified}")
    
    return 0


if __name__ == '__main__':
    exit(main())
