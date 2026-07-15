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

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def fetch_bilibili_trending():
    """获取B站科技区热门"""
    ret = []
    r = run(["curl", "-s", 
             "https://api.bilibili.com/x/web-interface/ranking/v2?rid=188&type=all",
             "-H", "User-Agent: Mozilla/5.0"])
    try:
        data = json.loads(r.stdout)
        for v in data.get("data", {}).get("list", [])[:8]:
            ret.append(f"- [{v['title']}](https://www.bilibili.com/video/{v['bvid']})")
    except:
        pass
    return ret

def fetch_hackernews():
    """获取Hacker News热门"""
    ret = []
    r = run(["curl", "-s", 
             "https://hacker-news.firebaseio.com/v0/topstories.json"])
    try:
        ids = json.loads(r.stdout)[:10]
        for sid in ids:
            r2 = run(["curl", "-s", f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"])
            item = json.loads(r2.stdout)
            if item and item.get("title"):
                url = item.get("url", f"https://news.ycombinator.com/item?id={sid}")
                ret.append(f"- [{item['title']}]({url})")
    except:
        pass
    return ret

def search_news(keyword, count=5):
    """搜索新闻"""
    results = []
    # 用 web_search 的工具不可用，这里用 curl 搜 searxng 或直接 API
    # 改用 web_fetch 采集几个科技新闻站
    urls = [
        "https://www.36kr.com/newsflashes",
        "https://www.jiqizhixin.com/",
        "https://www.pingwest.com/",
    ]
    for url in urls:
        r = run(["curl", "-sL", url, "-H", "User-Agent: Mozilla/5.0"])
        if r.returncode == 0:
            # 提取标题类内容
            titles = re.findall(r'<h[23][^>]*>(.*?)</h[23]>', r.stdout, re.DOTALL)
            titles = [re.sub(r'<[^>]+>', '', t).strip() for t in titles]
            titles = [t for t in titles if len(t) > 5 and len(t) < 200]
            for t in titles[:3]:
                results.append(f"- {t}")
    return results

def build_news(today):
    """构建今日新闻"""
    date_str = today.strftime("%Y-%m-%d")
    
    content = f"""# 📰 每日新闻 - {date_str}

> 北京时间 {today.strftime('%H:%M')} 更新 · 过去24小时互联网动态
"""

    # 搜索AI新闻
    print("正在采集AI新闻...")
    ai_news = search_news("AI 人工智能")
    
    content += """
## 🤖 AI 动态
"""
    if ai_news:
        for item in ai_news:
            content += f"\n{item}"
    else:
        content += """
> ⏳ 暂无数据（脚本采集有限，后续优化）
"""

    # Hacker News
    print("正在采集Hacker News...")
    hn = fetch_hackernews()
    if hn:
        content += """
### 🌐 Hacker News 热门
"""
        for item in hn:
            content += f"\n{item}"

    # B站科技区
    print("正在采集B站科技热门...")
    bili = fetch_bilibili_trending()
    if bili:
        content += """
### 📺 B站科技区热门
"""
        for item in bili:
            content += f"\n{item}"

    # 大厂动态
    content += """
## 🏢 国内大厂动态
"""
    big_tech = search_news("大厂 科技 动态")
    if big_tech:
        for item in big_tech:
            content += f"\n{item}"
    else:
        content += """
> ⏳ 暂无数据（脚本采集有限，后续优化）
"""

    content += f"""
---

*🤖 由 OpenClaw 自动整理 · {date_str}*
"""
    return content

def main():
    now = datetime.now(CST)
    
    # 如果是凌晨运行，往前一天
    if now.hour < 6:
        news_date = now - timedelta(days=1)
    else:
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
    
    # 更新README（添加链接）
    readme_path = REPO_DIR / "README.md"
    readme_content = readme_path.read_text(encoding="utf-8")
    
    # 在README中添加当天链接（如果还没有）
    link_line = f"- [{date_str}]({year}/{month}/{date_str}.md)"
    if link_line not in readme_content:
        # 在第二行后插入
        lines = readme_content.split("\n")
        idx = 2
        for i, line in enumerate(lines):
            if line.startswith("##"):
                idx = i
                break
        if idx < len(lines):
            # 看是否已有 ## 近期
            has_section = any("近期" in l for l in lines)
            if not has_section:
                lines.insert(idx, "")
                lines.insert(idx+1, "## 📅 近期新闻")
                idx = idx+2
            
            # 找到 ## 近期新闻 后面插入
            for i in range(idx, len(lines)):
                if lines[i].startswith("##") and "近期" not in lines[i]:
                    lines.insert(i, link_line)
                    break
            else:
                lines.append(link_line)
        
        readme_path.write_text("\n".join(lines), encoding="utf-8")
    
    # Git提交推送
    repo = REPO_DIR
    run(["git", "-C", str(repo), "add", "."])
    run(["git", "-C", str(repo), "commit", "-m", f"📰 每日新闻 {date_str}"])
    result = run(["git", "-C", str(repo), "push", "origin", "main"])
    
    if "nothing to commit" in result.stdout or result.returncode == 0:
        print(f"✅ 已推送至 GitHub: {date_str}" if result.returncode == 0 else "（没有新内容，跳过）")
    else:
        print(f"❌ 推送失败: {result.stderr}")

if __name__ == "__main__":
    main()
