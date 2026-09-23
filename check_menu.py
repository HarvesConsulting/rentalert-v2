from rentalert.bot import keyboards as kb

print("=== main_menu (uk) ===")
for row in kb.main_menu_keyboard("uk")["keyboard"]:
    print(f"  {[b['text'] for b in row]}")
print()

print("=== main_menu (en) ===")
for row in kb.main_menu_keyboard("en")["keyboard"]:
    print(f"  {[b['text'] for b in row]}")
print()

print("=== settings_keyboard (uk) ===")
for row in kb.settings_keyboard("🇺🇦 Україна", 9, 10, "uk")["inline_keyboard"]:
    print(f"  {[b['text'] for b in row]}")
