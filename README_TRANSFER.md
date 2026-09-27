# Перенесення застосунку «Перекладач»

## Варіант для іншого ПК

1. Скопіюйте `dist\Translator.exe` на інший ПК.
2. Python та бібліотеки встановлювати не потрібно.
3. Запустіть `Translator.exe`.
4. Для роботи Gemini задайте змінну середовища `GEMINI_API_KEY`.
5. Для резервного Claude задайте `ANTHROPIC_API_KEY`.

Для перекладу та виправлення тексту використовуйте Gemini або Claude. Якщо Gemini недоступний через ліміт, програма автоматично спробує Claude.

У PowerShell для поточного сеансу:

```powershell
$env:GEMINI_API_KEY = "ваш Gemini API ключ"
$env:ANTHROPIC_API_KEY = "ваш Anthropic API ключ"
.\Translator.exe
```

Для запуску через ярлик збережіть змінні середовища як системні або користувацькі змінні Windows, потім перезапустіть Explorer/застосунок.

## Збірка заново

На ПК розробника виконайте:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Готовий файл з'явиться у `dist\Translator.exe`.

## Безпека ключів

Не додавайте API-ключі до EXE, git або публічної папки. Ключі, які раніше були записані безпосередньо у `translator.py`, слід відкликати в Google AI Studio та Anthropic Console і створити нові.
