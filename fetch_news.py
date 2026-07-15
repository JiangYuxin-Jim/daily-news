#!/usr/bin/env python3
"""每日互联网新闻采集脚本 - 每天早上9点运行"""

import subprocess
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_DIR = Path("/home/admin/code/daily-news")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
CST = timezone(timedelta(hours=8))

def run(cmd, timeout=15, **kw):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
    except subprocess.TimeoutExpired:
        return None

def fetch_36kr():
    """获取36氪快讯"""
    r = run(["curl", "-sL", "--max-time", "8",
             "https://www.36kr.com/newsflashes",
             "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"])
    if not r or r.returncode != 0:
        return []
    
    # 提取JSON数据
    items = re.findall(r'"newsflashTitle":\{"title":"([^"]+)"', r.stdout)
    items = [i.encode('utf-8').decode('unicode_escape') for i in items]
    return items[:6]

def fetch_hn():
    """Hacker News top stories"""
    r = run(["curl", "-s", "--max-time", "8",
             "https://hacker-news.firebaseio.com/v0/topstories.json"])
    if not r:
        return []
    try:
        ids = json.loads(r.stdout)[:8]
    except:
        return []
    
    result = []
    for sid in ids:
        r2 = run(["curl", "-s", "--max-time", "5",
                  f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"])
        if not r2:
            continue
        try:
            item = json.loads(r2.stdout)
            if item and item.get("title"):
                url = item.get("url", f"https://news.ycombinator.com/item?id={sid}")
                result.append(f"- [{item['title']}]({url})")
        except:
            pass
    return result

def fetch_bili():
    """B站科技区热门"""
    r = run(["curl", "-s", "--max-time", "8",
             "https://api.bilibili.com/x/web-interface/ranking/v2?rid=188&type=all",
             "-H", "User-Agent: Mozilla/5.0"])
    if not r:
        return []
    try:
        data = json.loads(r.stdout)
        items = []
        for v in data.get("data", {}).get("list", [])[:5]:
            items.append(f"- [{v['title']}](https://www.bilibili.com/video/{v['bvid']})")
        return items
    except:
        return []

def ai_topic_news():
    """从36氪快讯中筛选AI相关"""
    news = fetch_36kr()
    ai_keywords = ["AI", "人工智能", "大模型", "GPT", "ChatGPT", "OpenAI", "谷歌", "微软",
                   "Claude", "字节", "百度", "阿里", "腾讯", "华为", "芯片", "算力",
                   "机器学习", "深度", "机器人", "自动驾驶", "大语言模型", "LLM",
                   "Midjourney", "Stable Diffusion", "Sora", "Copilot", "Gemini"]
    
    ai_news = []
    other_news = []
    
    for n in news:
        is_ai = any(kw.lower() in n.lower() for kw in ai_keywords)
        if is_ai:
            ai_news.append(f"- {n}")
        else:
            other_news.append(f"- {n}")
    
    return ai_news, other_news

def build_news(today):
    """构建今日新闻"""
    date_str = today.strftime("%Y-%m-%d")
    
    content = f"""# 📰 每日新闻 - {date_str}

> 北京时间 {today.strftime('%H:%M')} 更新 · 过去24小时互联网动态
"""
    
    print("正在采集AI新闻...")
    ai_news, other_news = ai_topic_news()
    
    content += "\n## 🤖 AI 动态\n\n"
    if ai_news:
        content += "\n".join(ai_news) + "\n"
    else:
        content += "> 本次未采集到AI相关新闻\n"
    
    # Hacker News
    print("正在采集Hacker News...")
    hn = fetch_hn()
    if hn:
        content += "\n### 🌐 Hacker News 热门\n\n"
        content += "\n".join(hn) + "\n"
    
    # B站
    print("正在采集B站科技热门...")
    bili = fetch_bili()
    if bili:
        content += "\n### 📺 B站科技区热门\n\n"
        content += "\n".join(bili) + "\n"
    
    content += "\n## 🏢 国内大厂动态\n\n"
    if other_news:
        content += "\n".join(other_news) + "\n"
    else:
        content += "> 本次未采集到大厂相关新闻\n"
    
    content += f"""
---

*🤖 由 OpenClaw 自动整理 · {date_str}*
"""
    return content

def main():
    now = datetime.now(CST)
    news_date = now
    
    content = build_news(news_date)
    
    year = news_date.strftime("%Y")
    month = news_date.strftime("%m")
    date_str = news_date.strftime("%Y-%m-%d")
    
    # 创建目录
    news_dir = REPO_DIR / year / month
    news_dir.mkdir(parents=True, exist_ok=True)
    
    # 写入文件
    filepath = news_dir / f"{date_str}.md"
    filepath.write_text(content, encoding="utf-8")
    print(f"✅ 已生成: {filepath}")
    
    # 更新README
    readme_path = REPO_DIR / "README.md"
    readme_content = readme_path.read_text(encoding="utf-8")
    
    link_line = f"- [{date_str}]({year}/{month}/{date_str}.md)"
    if link_line not in readme_content:
        # 找插入位置
        lines = readme_content.split("\n")
        
        # 找 ## 近期新闻 或文件末尾
        insert_idx = len(lines)
        for i, line in enumerate(lines):
            if line.startswith("## ") and "近期" in line:
                insert_idx = i + 1
                # 跳过空行
                while insert_idx < len(lines) and lines[insert_idx].strip() == "":
                    insert_idx += 1
                break
            if line.startswith("## ") and "近期" not in line and "每日" not in line:
                pass
        
        # 如果还没有近期新闻区块
        has_news_section = any("近期" in l for l in lines)
        if not has_news_section:
            # 在第二段后插入
            lines.append("")
            lines.append("## 📅 近期新闻")
            lines.append("")
            lines.append(link_line)
        else:
            lines.insert(insert_idx, link_line)
        
        readme_path.write_text("\n".join(lines), encoding="utf-8")
    
    # Git 提交推送
    repo = REPO_DIR
    token_cmd = f"https://JiangYuxin-Jim:{TOKEN}@github.com/JiangYuxin-Jim/daily-news.git"
    
    run(["git", "-C", str(repo), "remote", "set-url", "origin", token_cmd])
    run(["git", "-C", str(repo), "add", "."])
    
    commit = run(["git", "-C", str(repo), "commit", "-m", f"📰 每日新闻 {date_str}"])
    
    push = run(["git", "-C", str(repo), "push", "origin", "main"], timeout=30)
    
    if push and push.returncode == 0:
        print(f"✅ 已推送至 GitHub: {date_str}")
    elif commit and "nothing to commit" in commit.stdout:
        print("（没有新内容，跳过）")
    else:
        err = push.stderr if push else "push timeout"
        print(f"❌ 推送失败: {err[:200]}")

if __name__ == "__main__":
    main()
