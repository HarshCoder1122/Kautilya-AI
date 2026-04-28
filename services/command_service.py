"""
Kautilya AI — Command Service
Cloud command execution: weather, search, image, file ops, etc.
SECURITY FIX: safe_eval hardened with depth limit and power cap.
"""
import os
import re
import ast
import json
import requests

from config import NVIDIA_API_KEY, SERPAPI_API_KEY, MAPPLS_API_KEY


def find_balanced_command(text, start_index):
    count = 0
    in_quote = False
    quote_char = None
    escaped = False
    for i in range(start_index, len(text)):
        char = text[i]
        if escaped:
            escaped = False
            continue
        if char == '\\':
            escaped = True
            continue
        if char in ["'", '"']:
            if not in_quote:
                in_quote = True
                quote_char = char
            elif char == quote_char:
                in_quote = False
                quote_char = None
        if not in_quote:
            if char == '[':
                count += 1
            elif char == ']':
                count -= 1
            if count == 0:
                return i
    return -1


def is_safe_path(path, root=None):
    if not root:
        root = os.getcwd()
    try:
        abs_root = os.path.abspath(root)
        abs_path = os.path.abspath(os.path.join(abs_root, path))
        if not abs_path.startswith(abs_root):
            return False
        filename = os.path.basename(abs_path).lower()
        path_parts = abs_path.replace(abs_root, "").split(os.sep)
        if any(part.startswith('.') and part not in ('.', '..') for part in path_parts if part):
            return False
        blocklist = {
            "serviceaccountkey.json", "firebase_config.json",
            "app.py", "limits_manager.py", "make_pro.py",
            "requirements.txt", "package.json", "package-lock.json",
            ".env", "config.json", "agent_history.txt"
        }
        if filename in blocklist:
            return False
        sensitive_extensions = (
            '.json', '.env', '.log', '.key', '.crt', '.pem',
            '.bak', '.old', '.tmp', '.sql', '.db', '.sqlite'
        )
        if filename.endswith(sensitive_extensions):
            if filename not in ("manifest.json", "firebase.json"):
                return False
        return True
    except:
        return False


def extract_commands_balanced(text):
    commands = []
    cmd_pattern = re.compile(
        r'\[(IMAGE|SEARCH|WEATHER|NEWS|STOCK|PREDICT_STOCK|CRYPTO|MOVIE|CALCULATE|QUOTE|FACT|DEFINE|'
        r'TRANSLATE|CONVERT|CURRENCY|WIKI|HOROSCOPE|RECIPE|MAP|ROUTE|CREATE_FILE|WRITE_FILE|EDIT_FILE|'
        r'READ_FILE|LIST_FILES|LIST_DIR|TREE|DELETE_FILE|MOVE_FILE|MAKEDIRS|SHELL_EXEC|FETCH_DOCS|'
        r'INSTALL_SKILL|SELF_OPTIMIZE|HISTORY|FINISH)(?::|\\])'
    )
    pos = 0
    while pos < len(text):
        match = cmd_pattern.search(text, pos)
        if not match:
            break
        start = match.start()
        end = find_balanced_command(text, start)
        if end != -1:
            full_cmd = text[start:end+1]
            cmd_type = match.group(1)
            if full_cmd.startswith(f"[{cmd_type}:"):
                content = full_cmd[len(cmd_type)+2:-1]
            else:
                content = ""
            commands.append((full_cmd, cmd_type, content))
            pos = end + 1
        else:
            pos = match.end()
    return commands


def _safe_eval(node, depth=0):
    """HARDENED: safe math eval with depth limit and power cap."""
    MAX_DEPTH = 20
    if depth > MAX_DEPTH:
        raise ValueError(f"Expression too deeply nested (max {MAX_DEPTH})")
    if isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        left = _safe_eval(node.left, depth + 1)
        right = _safe_eval(node.right, depth + 1)
        if isinstance(node.op, ast.Add): return left + right
        if isinstance(node.op, ast.Sub): return left - right
        if isinstance(node.op, ast.Mult): return left * right
        if isinstance(node.op, ast.Div): return left / right
        if isinstance(node.op, ast.Pow):
            if abs(right) > 100:
                raise ValueError("Power operand too large (max 100)")
            return left ** right
        if isinstance(node.op, ast.Mod): return left % right
    if isinstance(node, ast.UnaryOp):
        operand = _safe_eval(node.operand, depth + 1)
        if isinstance(node.op, ast.UAdd): return +operand
        if isinstance(node.op, ast.USub): return -operand
    raise ValueError(f"Unsupported operation: {type(node)}")


def execute_cloud_commands(response_text, uid=None):
    """Parse JARVIS response for command tags and execute cloud-safe ones."""
    from extensions import limit_manager
    results = []
    found_commands = []
    commands = extract_commands_balanced(response_text)

    for full_cmd, cmd_type, content in commands:
        if cmd_type == "WEATHER":
            city = content.strip()
            found_commands.append(f"WEATHER:{city}")
            try:
                resp = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
                if resp.status_code == 200:
                    current = resp.json().get("current_condition", [{}])[0]
                    results.append(
                        f"\n🌤️ **Weather in {city}**: {current.get('weatherDesc', [{}])[0].get('value', 'Unknown')}\n"
                        f"🌡️ Temperature: {current.get('temp_C', '?')}°C (feels like {current.get('FeelsLikeC', '?')}°C)\n"
                        f"💧 Humidity: {current.get('humidity', '?')}% | 💨 Wind: {current.get('windspeedKmph', '?')} km/h"
                    )
            except Exception as e:
                results.append(f"\n⚠️ Could not fetch weather for {city}: {e}")

        elif cmd_type == "NEWS":
            found_commands.append("NEWS")
            try:
                resp = requests.get("https://saurav.tech/NewsAPI/top-headlines/category/general/in.json", timeout=10)
                if resp.status_code == 200:
                    articles = resp.json().get("articles", [])[:5]
                    news_lines = ["📰 **Top Headlines:**"]
                    for i, a in enumerate(articles, 1):
                        news_lines.append(f"{i}. {a.get('title', 'No title')}" + (f" — *{a.get('source', {}).get('name', '')}*" if a.get('source', {}).get('name') else ""))
                    results.append("\n" + "\n".join(news_lines))
            except Exception as e:
                results.append(f"\n⚠️ Could not fetch news: {e}")

        elif cmd_type == "STOCK":
            symbol = content.strip().upper()
            found_commands.append(f"STOCK:{symbol}")
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                if resp.status_code == 200:
                    meta = resp.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                    price = meta.get("regularMarketPrice", "N/A")
                    prev = meta.get("previousClose", 0)
                    change = round(price - prev, 2) if isinstance(price, (int, float)) and prev else "?"
                    pct = round((change / prev) * 100, 2) if prev else "?"
                    results.append(f"\n📈 **{meta.get('shortName', symbol)}** ({symbol})\n💰 Price: {price} {meta.get('currency', 'USD')}\n{'🟢' if change >= 0 else '🔴'} Change: {change} ({pct}%)")
                else:
                    results.append(f"\n⚠️ Could not fetch stock data for {symbol}")
            except Exception as e:
                results.append(f"\n⚠️ Stock error: {e}")

        elif cmd_type == "IMAGE":
            if not limit_manager.check_image_limit(uid, limit_per_day=3):
                results.append("\n🚫 **Daily Limit Reached**: 3 images/day for free tier.")
                continue
            prompt = content.strip()
            if prompt.lower() == "prompt":
                continue
            found_commands.append(f"IMAGE:{prompt[:20]}...")
            limit_manager.increment_image_count(uid)
            try:
                import base64
                resp = requests.post(
                    "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b",
                    headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Accept": "application/json", "Content-Type": "application/json"},
                    json={"prompt": prompt}, timeout=60
                )
                if resp.status_code == 200:
                    res_data = resp.json()
                    b64 = None
                    for key_path in [('data', 0), ('images', 0), ('artifacts', 0)]:
                        container = res_data.get(key_path[0])
                        if isinstance(container, list) and len(container) > 0:
                            item = container[0]
                            if isinstance(item, dict):
                                b64 = item.get('b64_json') or item.get('image') or item.get('b64') or item.get('base64') or item.get('data') or item.get('url')
                            elif isinstance(item, str):
                                b64 = item
                            if b64:
                                break
                    if not b64:
                        b64 = res_data.get('image') or res_data.get('b64_json') or res_data.get('b64') or res_data.get('base64')
                    if b64:
                        img_url = b64 if b64.startswith('http') or b64.startswith('data:') else f"data:image/png;base64,{b64}"
                        results.append(f"\n🎨 Here's your generated image:\n\n[IMG_URL:{img_url}]")
                    else:
                        results.append("\n⚠️ Image generation returned no data.")
                else:
                    results.append(f"\n⚠️ **NVIDIA Image Error**: {resp.status_code}")
            except Exception as e:
                results.append("\n🎨 **Image generation failed.** Please check NVIDIA API availability.")

        elif cmd_type == "CRYPTO":
            crypto = content.strip().lower()
            found_commands.append(f"CRYPTO:{crypto}")
            try:
                resp = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={crypto}&vs_currencies=usd,inr&include_24hr_change=true", timeout=10)
                if resp.status_code == 200 and crypto in resp.json():
                    data = resp.json()[crypto]
                    change = data.get("usd_24h_change", 0)
                    results.append(f"\n💰 **{crypto.title()}**\n💵 ${data.get('usd', '?'):,} USD | ₹{data.get('inr', '?'):,} INR\n{'🟢' if change >= 0 else '🔴'} 24h Change: {change:.2f}%")
                else:
                    results.append(f"\n⚠️ Cryptocurrency '{crypto}' not found.")
            except Exception as e:
                results.append(f"\n⚠️ Crypto lookup error: {e}")

        elif cmd_type == "WIKI":
            topic = content.strip()
            found_commands.append(f"WIKI:{topic}")
            try:
                resp = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic}", headers={"User-Agent": "KAUTILYA-AI/1.0"}, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    results.append(f"\n📚 **{data.get('title', topic)}**\n{data.get('extract', 'No summary.')[:500]}")
            except Exception as e:
                results.append(f"\n⚠️ Wikipedia error: {e}")

        elif cmd_type == "CALCULATE":
            expr = content.strip()
            found_commands.append(f"CALCULATE:{expr}")
            if len(expr) > 200:
                results.append("\n⚠️ Expression too long (max 200 chars)")
                continue
            try:
                tree = ast.parse(expr.replace("^", "**").replace("%", "/100"), mode='eval')
                result = _safe_eval(tree.body)
                results.append(f"\n🔢 **Result**: {expr} = {result}")
            except Exception as e:
                results.append(f"\n⚠️ Calculation error: {e}")

        elif cmd_type == "SEARCH":
            query = content.strip()
            found_commands.append(f"SEARCH:{query}")
            try:
                if SERPAPI_API_KEY:
                    from serpapi import GoogleSearch
                    organic = GoogleSearch({"q": query, "api_key": SERPAPI_API_KEY, "num": 3}).get_dict().get("organic_results", [])
                    if organic:
                        results.append("\n" + "\n".join([f"🔍 **Search results for '{query}':**"] + [f"• {r.get('title')}: {r.get('snippet')}" for r in organic]))
                    else:
                        results.append(f"\n🔍 No results for '{query}'.")
                else:
                    results.append(f"\n⚠️ Search unavailable (no API key).")
            except Exception as e:
                results.append(f"\n⚠️ Search error: {e}")

        elif cmd_type == "MAP":
            location = content.strip()
            found_commands.append(f"MAP:{location}")
            encoded_loc = requests.utils.quote(location)
            if MAPPLS_API_KEY:
                results.append(f"\n🗺️ **Map of {location}**: [Open in Mapples](https://maps.mapmyindia.com/explore/{encoded_loc})")
            else:
                results.append(f"\n🗺️ **Map of {location}**: [Open in Google Maps](https://www.google.com/maps/search/?api=1&query={encoded_loc})")

        elif cmd_type == "QUOTE":
            found_commands.append("QUOTE")
            try:
                resp = requests.get("https://zenquotes.io/api/random", timeout=5)
                if resp.status_code == 200:
                    q = resp.json()[0]
                    results.append(f'\n💬 *"{q.get("q", "")}"*\n— {q.get("a", "Unknown")}')
            except:
                pass

        elif cmd_type == "FACT":
            found_commands.append("FACT")
            try:
                resp = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random", timeout=5)
                if resp.status_code == 200:
                    results.append(f"\n🧠 **Fun Fact**: {resp.json().get('text', '')}")
            except:
                pass

        elif cmd_type == "DEFINE":
            word = content.strip()
            found_commands.append(f"DEFINE:{word}")
            try:
                resp = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=10)
                if resp.status_code == 200:
                    meaning = resp.json()[0].get("meanings", [{}])[0]
                    defn = meaning.get("definitions", [{}])[0]
                    results.append(f"\n📖 **{word}** ({meaning.get('partOfSpeech', '')}): {defn.get('definition', '')}" + (f"\n*Example: {defn.get('example')}*" if defn.get('example') else ""))
            except:
                results.append(f"\n⚠️ Definition not found for '{word}'")

        elif cmd_type == "TRANSLATE":
            parts = content.split("|")
            if len(parts) == 2:
                text_to_translate, target = [p.strip() for p in parts]
                found_commands.append(f"TRANSLATE:{target}")
                lang_map = {"hindi": "hi", "spanish": "es", "french": "fr", "german": "de", "japanese": "ja", "chinese": "zh", "korean": "ko", "arabic": "ar", "tamil": "ta"}
                lang_code = lang_map.get(target.lower(), target[:2])
                try:
                    resp = requests.get(f"https://api.mymemory.translated.net/get?q={text_to_translate}&langpair=en|{lang_code}", timeout=10)
                    if resp.status_code == 200:
                        translated = resp.json().get("responseData", {}).get("translatedText", "")
                        if translated:
                            results.append(f'\n🌐 **Translation** ({target}):\n"{translated}"')
                except Exception as e:
                    results.append(f"\n⚠️ Translation error: {e}")

        elif cmd_type == "CONVERT":
            parts = content.split("|")
            if len(parts) == 3:
                value, from_u, to_u = [p.strip().lower() for p in parts]
                found_commands.append(f"CONVERT:{value}|{from_u}|{to_u}")
                conversions = {
                    ("km", "miles"): 0.621371, ("miles", "km"): 1.60934,
                    ("kg", "lbs"): 2.20462, ("lbs", "kg"): 0.453592,
                    ("cm", "inches"): 0.393701, ("inches", "cm"): 2.54,
                    ("m", "feet"): 3.28084, ("feet", "m"): 0.3048,
                    ("c", "f"): lambda v: v * 9/5 + 32, ("f", "c"): lambda v: (v - 32) * 5/9,
                    ("l", "gallon"): 0.264172, ("gallon", "l"): 3.78541,
                }
                try:
                    val = float(value)
                    factor = conversions.get((from_u, to_u))
                    if factor:
                        converted = factor(val) if callable(factor) else val * factor
                        results.append(f"\n📏 {value} {from_u} = **{converted:.2f} {to_u}**")
                    else:
                        results.append(f"\n⚠️ Conversion from {from_u} to {to_u} not supported")
                except:
                    results.append(f"\n⚠️ Invalid value: {value}")

        elif cmd_type == "CURRENCY":
            parts = content.split("|")
            if len(parts) == 3:
                amount, from_c, to_c = [p.strip() for p in parts]
                found_commands.append(f"CURRENCY:{amount}|{from_c}|{to_c}")
                try:
                    resp = requests.get(f"https://open.er-api.com/v6/latest/{from_c}", timeout=10)
                    if resp.status_code == 200:
                        rate = resp.json().get("rates", {}).get(to_c)
                        if rate:
                            results.append(f"\n💱 {amount} {from_c} = **{float(amount) * rate:.2f} {to_c}**")
                except Exception as e:
                    results.append(f"\n⚠️ Currency conversion error: {e}")

        elif cmd_type == "ROUTE":
            parts = content.split("|")
            if len(parts) == 2:
                origin, dest = [p.strip() for p in parts]
                found_commands.append(f"ROUTE:{origin}->{dest}")
                if MAPPLS_API_KEY:
                    results.append(f"\n🚗 **Route from {origin} to {dest}**\n🔗 [View on Mapples](https://maps.mapmyindia.com/directions/{origin}/{dest})")
                else:
                    results.append(f"\n🚗 **Route from {origin} to {dest}**\n🔗 [Open in Google Maps](https://www.google.com/maps/dir/?api=1&origin={requests.utils.quote(origin)}&destination={requests.utils.quote(dest)})")

        elif cmd_type == "RECIPE":
            dish = content.strip()
            found_commands.append(f"RECIPE:{dish}")
            try:
                resp = requests.get(f"https://www.themealdb.com/api/json/v1/1/search.php?s={dish}", timeout=10)
                if resp.status_code == 200:
                    meals = resp.json().get("meals")
                    if meals:
                        m = meals[0]
                        ingredients = []
                        for i in range(1, 10):
                            ing = m.get(f"strIngredient{i}", "").strip()
                            measure = m.get(f"strMeasure{i}", "").strip()
                            if ing:
                                ingredients.append(f"  • {measure} {ing}")
                        results.append(f"\n🍽️ **{m.get('strMeal')}** ({m.get('strArea', '')} cuisine)\n📋 Ingredients:\n" + "\n".join(ingredients[:8]))
            except Exception as e:
                results.append(f"\n⚠️ Recipe error: {e}")

        elif cmd_type == "MOVIE":
            title = content.strip()
            found_commands.append(f"MOVIE:{title}")
            omdb_key = os.environ.get("OMDB_API_KEY", "")
            if omdb_key:
                try:
                    resp = requests.get(f"http://www.omdbapi.com/?t={title}&apikey={omdb_key}", timeout=10)
                    if resp.status_code == 200:
                        m = resp.json()
                        if m.get("Response") == "True":
                            results.append(f"\n🎬 **{m.get('Title')}** ({m.get('Year')})\n⭐ IMDb: {m.get('imdbRating')}/10 | 🎭 {m.get('Genre')}\n🎥 Director: {m.get('Director')}\n👥 Cast: {m.get('Actors')}\n📝 {m.get('Plot')}")
                except Exception as e:
                    results.append(f"\n⚠️ Movie lookup error: {e}")

        elif cmd_type in ("CREATE_FILE", "WRITE_FILE"):
            parts = content.split("|", 1)
            if len(parts) >= 2:
                path = parts[0].strip().strip('"`\'')
                file_content = parts[1].strip()
                found_commands.append(f"{cmd_type}:{path}")
                if not is_safe_path(path):
                    results.append(f"\n🚫 **Security Block**: Access to `{path}` is restricted.")
                    continue
                try:
                    dir_name = os.path.dirname(path)
                    if dir_name:
                        os.makedirs(dir_name, exist_ok=True)
                    if cmd_type == "WRITE_FILE" and os.path.exists(path):
                        import shutil
                        shutil.copy2(path, path + ".bak")
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(file_content)
                    results.append(f"\n💾 **{'Overwritten' if cmd_type == 'WRITE_FILE' else 'Saved'} file**: `{path}`")
                except Exception as e:
                    results.append(f"\n⚠️ Could not create file '{path}': {e}")

        elif cmd_type == "READ_FILE":
            path = content.strip().strip('"`\'')
            found_commands.append(f"READ_FILE:{path}")
            if not is_safe_path(path):
                results.append(f"\n🚫 **Security Block**: Access to `{path}` is restricted.")
                continue
            try:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        output = f.read()
                    lines = output.splitlines()
                    numbered = "\n".join([f"{i+1}: {line}" for i, line in enumerate(lines)])
                    if len(numbered) > 8000:
                        numbered = numbered[:8000] + "\n...(truncated)"
                    results.append(f"\n📄 **Content of {os.path.basename(path)}**:\n```\n{numbered}\n```")
                else:
                    results.append(f"\n⚠️ File not found: `{path}`")
            except Exception as e:
                results.append(f"\n⚠️ Could not read file: {e}")

        elif cmd_type == "EDIT_FILE":
            parts = content.split("|")
            if len(parts) >= 3:
                path = parts[0].strip().strip('"`\'')
                old_string = parts[1].strip()
                new_string = parts[2].strip()
                found_commands.append(f"EDIT_FILE:{path}")
                if not is_safe_path(path):
                    results.append(f"\n🚫 **Security Block**: Access to `{path}` is restricted.")
                    continue
                try:
                    if not os.path.exists(path):
                        results.append(f"\n⚠️ File not found: {path}")
                        continue
                    with open(path, 'r', encoding='utf-8') as f:
                        fc = f.read()
                    count = fc.count(old_string)
                    if count == 0:
                        results.append(f"\n⚠️ Search string not found in `{path}`.")
                    elif count > 1:
                        results.append(f"\n⚠️ Found {count} occurrences. Please be more specific.")
                    else:
                        with open(path, 'w', encoding='utf-8') as f:
                            f.write(fc.replace(old_string, new_string))
                        results.append(f"\n✅ **Surgical Edit Applied**: `{path}`")
                except Exception as e:
                    results.append(f"\n⚠️ Edit error for '{path}': {e}")

        elif cmd_type == "LIST_DIR":
            path = content.strip().strip('"`\'') if content else "."
            found_commands.append(f"LIST_DIR:{path}")
            if not is_safe_path(path):
                results.append(f"\n🚫 **Security Block**: Access to `{path}` is restricted.")
                continue
            try:
                if os.path.exists(path) and os.path.isdir(path):
                    items = [i for i in os.listdir(path) if not i.startswith('.')]
                    results.append(f"\n📂 **Contents of {path}**:\n" + "\n".join([f"- {i}" for i in items[:20]]))
                else:
                    results.append(f"\n⚠️ Directory not found: `{path}`")
            except Exception as e:
                results.append(f"\n⚠️ Could not list directory: {e}")

        elif cmd_type in ("PREDICT_STOCK", "RUN_PYTHON", "HOROSCOPE"):
            found_commands.append(cmd_type)
            if cmd_type == "PREDICT_STOCK":
                results.append(f"\n📊 Stock prediction for **{content.strip().upper()}** is only available in the desktop version.")
            elif cmd_type == "RUN_PYTHON":
                results.append("\n⚠️ Server-side Python execution is disabled for security.")
            elif cmd_type == "HOROSCOPE":
                results.append(f"\n🔮 Horoscope for **{content.strip().title()}**: Ask me to tell your horoscope and I'll use my knowledge!")

    if found_commands:
        print(f"[Commands] Executed: {', '.join(found_commands)}")

    full_output = response_text
    if results:
        full_output += "\n" + "\n".join(results)
    return full_output
