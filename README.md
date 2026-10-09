# Dune: Spice Wars — українська локалізація

Неофіційний переклад українською. Не пов'язаний із Shiro Games чи Funcom.

![гра](https://img.shields.io/badge/гра-Steam-blue) ![статус](https://img.shields.io/badge/переклад-31%25-orange) ![версія](https://img.shields.io/badge/версія_гри-2.2.7-lightgrey)

[Dune: Spice Wars у Steam](https://store.steampowered.com/app/1605220/Dune_Spice_Wars/)

## Стан перекладу

Перекладено **5 713 з 18 204 рядків (31%)**. Неперекладене гра показує англійською.

| Розділ | Стан |
|---|---|
| Інтерфейс: меню, підказки, Ландсраад, ринок ДАПТ, шпигунство, дипломатія, торгівля, «Завоювання», налаштування | готово |
| Ресурси: назви, усі відмінки, описи | готово |
| Фракції: назви, відмінки, описи | готово |
| Бойові одиниці: назви з усіма відмінками й множиною | готово, описи — ні |
| Шрифти: літери Ї, Є, Ґ у всіх 8 шрифтах гри | готово |
| Будівлі, споруди, регіони | далі в черзі |
| Риси, здібності, розробки, спорядження | — |
| Навчання, місії, події, репліки персонажів | — |

Переклад іде з англійського оригіналу.

## Встановлення

Готової збірки поки немає: переклад у роботі. Коли вийде, її можна буде завантажити зі сторінки [Releases](../../releases).

## Видалення

```
py tools/build.py --uninstall
```

Або просто видаліть `res.compressed1.pak` з папки гри. Оригінальні файли гри не змінюються ні за встановлення, ні за видалення. Перевірка цілісності в Steam цей файл не прибирає — його треба видалити самому.

## Чому слот французької

Список мов вкомпільований у код гри (`hlboot.dat`), і гра показує лише мови з цього списку. Додати окремий пункт «Українська» можна тільки патчем виконуваного коду, а англійська взагалі не завантажує файлів перекладу. Тому переклад займає слот французької мови: код гри не робить для неї жодних винятків, а стилі інтерфейсу дають їй ширші кнопки й панелі під довший текст. У меню вибору мови він підписаний «Français». Решта мов гри не використовуються й не змінюються.

## Відомі обмеження

- Поки що перекладено близько третини тексту; решта — англійською.
- Назви, які гра не вміє відмінювати (риси, дипломатичні статуси, території), у реченнях стоять у лапках або в називному відмінку.
- Патч змінює лише тексти й шрифти на вашому комп'ютері. У мережевій грі окремо не перевірявся.
- Після оновлення гри нові чи змінені англійські рядки показуються англійською, доки їх не перекладуть: інструменти помічають такі рядки самі.

## Як це влаштовано

Гра зроблена на рушії Heaps (HashLink). Усе нижче з'ясовано розбором її файлів і байткоду.

**Патч одним файлом.** Ресурси лежать у `res.compressed.pak`. Після нього гра шукає `res.compressed1.pak`, `res.compressed2.pak`… і файли з тими самими шляхами бере з них. Тому переклад — один файл поруч з оригіналом, який нічого в ньому не змінює.

**Тексти.** Інтерфейс — у `texts.xml`, усе інше — у базі `data.cdb` (CastleDB). Переклади лежать у `lang/texts_<мова>.xml` і `lang/export_<мова>.xml`.

**Еталонний англійський.** Для кожного рядка гра звіряє англійський текст, з якого його перекладали (`lang/old/export_<мова>_old.xml`), з поточним англійським — і мовчки відкидає переклад, якщо вони розійшлися. Тому збирання кладе в патч власний еталон, згенерований з вашої копії гри, а кожен рядок перекладу зберігає відбиток англійського оригіналу: застарілий переклад не потрапить у гру.

**Відмінки.** Гра підставляє назви в текст посиланнями на кшталт `[Spice]` із суфіксом відмінка. Для кожної назви в перекладі є 12 форм — шість відмінків в однині й множині — плюс окрема множина:

| Суфікс | Форма | Приклад |
|---|---|---|
| — | назва | Прянощі |
| `g` | родовий | прянощів |
| `d` | давальний | прянощам |
| `a` | знахідний | прянощі |
| `i` | орудний | прянощами |
| `pr` | місцевий | прянощах |
| `l`, `lc` | називний з малої | прянощі |
| `p`, `s` | множина | Прянощі |

Додане `p` чи `s` робить відмінок множинним: `gp` — родовий множини.

**Шрифти.** Гра використовує 8 шрифтів: шість багатоканальних полів відстаней (MSDF) і два растрові з тінню. Кирилиця в них є, але бракує `Ї ї Є є Ґ ґ`. Збирання дописує ці літери з наявних гліфів того ж шрифту:

| Літера | З чого |
|---|---|
| `ї` | латинська `ï` |
| `Ї` | `І` + дві крапки з `Ï` |
| `Є`, `є` | дзеркальні `Э`, `э` з відступами як у `С` (у курсиві — з відновленим нахилом) |
| `Ґ`, `ґ` | `Г`, `г` + вертикальний штрих завтовшки зі стовбур літери |

Тінь растрових шрифтів перемальовується за моделлю, підібраною за наявними літерами (похибка менше 1%). Нові гліфи дописуються смугою під атласом, тож жодна стара літера не зсувається.

**Нічого з гри не поширюється.** Репозиторій містить лише інструменти. Шрифти, еталонний англійський і готовий патч генеруються на вашому комп'ютері з вашої копії гри.

## Термінологія

Канон — український переклад «Дюни» Френка Герберта (КСД, переклад Анатолія Пітика й Катерини Грицайчук): **прянощі, січ, ДАПТ, Атріди, Бене Ґессерит, Гільдія Лоцманів, гупало, транспортувальник, Ландсраад**. Терміни, яких у книзі немає, утворено за її зразком: **пласкрит, Картаґ, Дім Верніусів**.

Глосарій ведеться разом із перекладом і до репозиторію не входить.

## Структура

| Шлях | Що це |
|---|---|
| `translation/` (не в репозиторії) | переклад (ключ, відбиток англійського оригіналу, український текст) і глосарій; зберігаються окремо |
| `tools/build.py` | збирає патч (тексти + шрифти) і встановлює чи видаляє його |
| `tools/check.py` | перевіряє переклад |
| `tools/extract.py` | витягає англійський текст гри в `local/` для роботи |
| `tools/merge.py` | вливає нову порцію перекладу |
| `tools/review.py` | вивантажує переклад у таблицю Excel для вичитки й забирає правки назад |
| `tools/fonts.py`, `tools/bfnt.py`, `tools/preview.py` | шрифти: додавання літер, формат BFNT, попередній перегляд |
| `tools/d4x.py` | спільна бібліотека: формат PAK, мовні XML, обхід `data.cdb` |

Папка `local/` (не в репозиторії) містить текст самої гри — для роботи, не для поширення.

## Як долучитися

Зауваження до перекладу — через Issues: назва рядка або скриншот і як має бути.

Хочете перекладати чи вичитувати — напишіть в Issues. Робочі файли перекладу не публікуються, доступ до них — за домовленістю. Надіслані правки входять до перекладу на умовах [LICENSE](LICENSE).

З доступом до робочих файлів:

```
py tools/extract.py                     витягти тексти гри в local/source/
py tools/merge.py <порція.tsv>          влити свої рядки в translation/
py tools/check.py -v                    перевірити й побачити поступ
py tools/build.py --install             зібрати й подивитися в грі
py tools/review.py <назва> <префікс>    таблиця для вичитки (і --import для правок)
```

Порція — текстовий файл: ключ, табуляція, переклад. Назву з усіма відмінками задає один рядок:

```
export:unit/A_Trooper/texts.name=forms	піхотинець; піхотинця; піхотинцеві; піхотинця; піхотинцем; піхотинцеві | піхотинці; піхотинців; піхотинцям; піхотинців; піхотинцями; піхотинцях
```

`check.py` не пропустить у гру рядок, у якому зникли змінні `::value::`, зламані теги `<good>`, невідомий суфікс після посилання чи символ, якого немає в шрифтах гри.

Стиль: звертання «ви» з малої; апостроф — звичайний `'` (типографського `’` у шрифтах гри немає); замість `№` — `#`; назва посеред речення — завжди з суфіксом відмінка (`[Spice]g`), а не голим `[Spice]`, інакше вона вийде з великої літери.

## Ліцензії

Код — MIT. Переклад і глосарій — усі права захищено: збірку можна завантажити з [Releases](../../releases) і встановити на власну копію гри; розміщення деінде (сайти, лаунчери, каталоги, збірки), використання як основи для інших перекладів і комерційне використання — лише з письмової згоди автора. Запит — через Issues. Деталі — у [LICENSE](LICENSE).

Гра має бути придбана. Репозиторій не містить жодного файлу гри.

Dune: Spice Wars © Shiro Games, видавець Funcom. Dune © Herbert Properties LLC.

---

# Dune: Spice Wars — Ukrainian localisation

An unofficial Ukrainian translation. Not affiliated with Shiro Games or Funcom.

**Status:** 5,713 of 18,204 strings (31%): the whole UI, resources, factions, unit names with every grammatical case, and the fonts (Ї, Є, Ґ added to all 8 game fonts). Buildings and regions come next. Anything untranslated shows in English.

## Installing

No release yet: the translation is in progress. Builds will be published on the [Releases](../../releases) page.

To remove a build: `py tools/build.py --uninstall`, or delete `res.compressed1.pak` from the game folder (Steam's integrity check leaves it in place).

## Why the French slot

The language list is compiled into the game code (`hlboot.dat`); a new entry would need a bytecode patch, and English loads no translation files at all. The translation therefore occupies the French slot: the code has no special cases for French, and the UI styles give it wider buttons and panels for longer text. The language picker labels it "Français". No other language of the game is used or changed.

## How it works

- **One patch file.** After `res.compressed.pak` the game mounts `res.compressed1.pak`, `res.compressed2.pak`…, whose files override the original paths. The translation is that one file; nothing original is touched.
- **Reference English.** For each line the game compares the English it was translated from (`lang/old/export_<lang>_old.xml`) with the current English, and silently drops the line if they differ. The build writes its own reference from your copy. Every translated line stores a fingerprint of its English source, so stale translations never ship.
- **Grammatical cases.** Names are inserted through links such as `[Spice]g`. The suffix picks one of 12 declension forms the translation provides for every name.
- **Fonts.** The 8 UI fonts (six multi-channel signed distance fields, two shadowed bitmaps) lack `Ї ї Є є Ґ ґ`. The build derives them from glyphs the same font already has (`ï`; `І` with the dots of `Ï`; a mirrored `Э`; `Г` plus an upturn). New glyphs go into a strip appended under the atlas.
- **Nothing from the game is distributed.** The repository holds the tools only. Fonts, the reference file and the patch are generated on your machine from your copy.

Terminology follows the Ukrainian edition of Frank Herbert's *Dune* (KSD).

## Licences

Code: MIT. Translation and glossary: all rights reserved. Download a build from [Releases](../../releases) and install it on your own copy; hosting it anywhere else (websites, launchers, catalogues, collections), using it as the basis for another translation, or any commercial use needs the author's written permission. Ask via Issues. See [LICENSE](LICENSE). You need to own the game; this repository contains no game files.
