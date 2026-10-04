content = open('main.py', encoding='utf-8').read()
bad = '    lines = [f"Here is a summary based on your question: "{req.question}""]'
good = "    lines = [f'Here is a summary based on your question: \"{req.question}\"']"
assert bad in content, f"Bad line not found! Got: {repr([l for l in content.splitlines() if 'Here is a summary' in l])}"
open('main.py', 'w', encoding='utf-8').write(content.replace(bad, good, 1))
print("fixed")
