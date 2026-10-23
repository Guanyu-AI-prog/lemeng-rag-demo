# -*- coding: utf-8 -*-
"""
合成示例评测题库（脱敏演示版）

原仓库的 kb30/kb60 题库对照真实企业知识库出题，不宜公开。
本文件为同 schema 的合成示例，品牌与业务细节均为虚构，
用于演示评测流水线的用法：题目 → 检索 → 生成 → 多维打分。

字段:
- id / type(单点查询|对比型|计算型|流程型|边界异常) / group
- question: 自然问法
- expected_keywords: 关键事实(召回率+完整性评分)
- reference: 参考答案
- anti_keywords: 幻觉检测词(答案中不应出现)
"""

SAMPLE_BRAND = "星芽少儿编程"  # 虚构品牌，仅用于演示

TEST_CASES = [
    {"id": 1, "type": "单点查询", "group": "sample",
     "question": "星芽少儿编程是什么时候成立的？",
     "expected_keywords": ["2020", "少儿编程"],
     "reference": "星芽少儿编程成立于2020年，专注少儿编程教育（虚构示例）",
     "anti_keywords": []},
    {"id": 2, "type": "单点查询", "group": "sample",
     "question": "星芽的课程适合几岁的孩子？",
     "expected_keywords": ["6-14", "岁"],
     "reference": "课程面向6-14岁孩子（虚构示例）",
     "anti_keywords": []},
    {"id": 3, "type": "对比型", "group": "sample",
     "question": "Scratch 启蒙课和 Python 进阶课有什么区别？",
     "expected_keywords": ["图形化", "代码", "Scratch", "Python"],
     "reference": "Scratch 启蒙课用图形化拖拽，适合零基础；Python 进阶课写真实代码，需要前置基础（虚构示例）",
     "anti_keywords": []},
    {"id": 4, "type": "计算型", "group": "sample",
     "question": "一年 48 课时的课包，每课时 150 元，总共多少钱？",
     "expected_keywords": ["7200"],
     "reference": "48×150=7200 元（虚构示例）",
     "anti_keywords": []},
    {"id": 5, "type": "流程型", "group": "sample",
     "question": "新生报名需要走哪些流程？",
     "expected_keywords": ["预约", "试听", "测评", "报名"],
     "reference": "预约 → 免费试听 → 能力测评 → 正式报名（虚构示例）",
     "anti_keywords": []},
    {"id": 6, "type": "单点查询", "group": "sample",
     "question": "请假后课程怎么补？",
     "expected_keywords": ["补课", "预约"],
     "reference": "提前预约即可安排补课（虚构示例）",
     "anti_keywords": []},
    {"id": 7, "type": "边界异常", "group": "sample",
     "question": "星芽有没有开设成人英语课？",
     "expected_keywords": ["没有", "少儿"],
     "reference": "星芽只做少儿编程，没有成人英语课（虚构示例）",
     "anti_keywords": ["成人英语报名方式", "英语课表"]},
    {"id": 8, "type": "单点查询", "group": "sample",
     "question": "上课需要自带电脑吗？",
     "expected_keywords": ["不需要", "机房"],
     "reference": "不需要，校区有机房设备（虚构示例）",
     "anti_keywords": []},
    {"id": 9, "type": "对比型", "group": "sample",
     "question": "线上课和线下课哪个效果好？",
     "expected_keywords": ["线下", "互动"],
     "reference": "低龄建议线下（互动强），高年级可选线上（虚构示例）",
     "anti_keywords": []},
    {"id": 10, "type": "计算型", "group": "sample",
     "question": "连报两年 96 课时打 9 折，比单报一年 48 课时省多少？",
     "expected_keywords": ["1440"],
     "reference": "96×150×0.9=12960，48×150=7200，两年省 14400-12960=1440 元（虚构示例）",
     "anti_keywords": []},
    {"id": 11, "type": "流程型", "group": "sample",
     "question": "退费要怎么申请？",
     "expected_keywords": ["申请", "审核", "原路退回"],
     "reference": "提交退费申请 → 审核 → 原路退回（虚构示例）",
     "anti_keywords": []},
    {"id": 12, "type": "边界异常", "group": "sample",
     "question": "星芽的创始人是谁？他喜欢吃什么？",
     "expected_keywords": ["创始人"],
     "reference": "知识库无创始人饮食偏好记录，不应编造（虚构示例）",
     "anti_keywords": ["红烧肉", "最爱吃"]},
]

# 兼容原 kb30 接口（KB30_QUESTIONS），取前 6 题
KB30_QUESTIONS = [
    {"question": c["question"], "expected_keywords": c["expected_keywords"],
     "reference": c["reference"]}
    for c in TEST_CASES[:6]
]
