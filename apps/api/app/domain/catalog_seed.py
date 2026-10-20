"""Default service catalog for NetNova.

The panel can edit, reorder, extend or archive every entry; this module only
provides a sensible starting tree so the bot is useful on day one instead of
showing an empty menu. Content is deliberately factual: it describes the
services and asks the questions the sales team needs, and never invents prices,
portfolios or delivery promises.
"""

from __future__ import annotations

from typing import Any

PORTFOLIO_HINT = (
    "برای مشاهده نمونه کارهای این بخش، پس از ثبت سفارش، نمونه های مرتبط "
    "توسط تیم نت نووا برای شما ارسال می شود."
)


def q(
    key: str,
    label: str,
    field_type: str = "text",
    *,
    options: list[str] | None = None,
    required: bool = True,
    min_value: int | None = None,
    max_value: int | None = None,
    help_text: str = "",
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "field_type": field_type,
        "options": options or [],
        "required": required,
        "min_value": min_value,
        "max_value": max_value,
        "help_text": help_text,
    }


def item(
    key: str,
    title: str,
    questions: list[dict[str, Any]],
    *,
    description: str = "",
    show_portfolio: bool = False,
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "description": description,
        "questions": questions,
        "show_portfolio": show_portfolio,
        "portfolio_text": PORTFOLIO_HINT if show_portfolio else "",
    }


WEB_QUESTIONS = [
    q(
        "domain",
        "وضعیت دامنه شما چگونه است؟",
        "choice",
        options=["دامنه دارم", "دامنه ندارم", "نیاز به مشاوره دارم"],
    ),
    q("pages", "حدودا چند صفحه لازم دارید؟", "number", min_value=1, max_value=500),
    q(
        "content_ready",
        "محتوا و تصاویر آماده است؟",
        "choice",
        options=["آماده است", "کمی آماده است", "آماده نیست"],
    ),
    q(
        "payment",
        "به درگاه پرداخت نیاز دارید؟",
        "choice",
        options=["بله", "نه", "بعدا تصمیم می گیرم"],
    ),
    q("details", "توضیحات تکمیلی درباره کسب و کار و انتظارات شما", "long_text", required=False),
]

APP_QUESTIONS = [
    q(
        "platform_note",
        "کاربران بیشتر با گوشی اندروید کار می کنند یا آیفون؟",
        "choice",
        options=["بیشتر اندروید", "بیشتر آیفون", "هر دو به یک اندازه"],
    ),
    q(
        "users",
        "تعداد کاربران تقریبی در سال اول چقدر است؟",
        "choice",
        options=["زیر ۱۰۰۰", "۱۰۰۰ تا ۱۰۰۰۰", "بیشتر از ۱۰۰۰۰"],
    ),
    q("features", "چه امکاناتی لازم دارید؟", "long_text"),
    q(
        "payment",
        "به درگاه پرداخت نیاز دارید؟",
        "choice",
        options=["بله", "نه", "بعدا تصمیم می گیرم"],
    ),
    q("details", "توضیحات تکمیلی", "long_text", required=False),
]

CONTENT_QUESTIONS = [
    q("language", "زبان محتوا", "choice", options=["فارسی", "انگلیسی", "عربی", "سایر زبان ها"]),
    q(
        "words",
        "تعداد کلمات هر مقاله",
        "number",
        min_value=800,
        max_value=20000,
        help_text="حداقل ۸۰۰ کلمه برای هر مقاله",
    ),
    q("articles", "تعداد مقالات", "number", min_value=1, max_value=500),
    q("field", "حوزه کاری سایت شما چیست؟"),
    q("site", "آدرس سایت (اگر دارید)", required=False),
    q(
        "topic",
        "موضوع مقالات مشخص است؟",
        "choice",
        options=["بله، موضوع مشخص است", "نه، مشاوره تیم محتوای نت نووا را می خواهم"],
    ),
]


DEFAULT_CATALOG: list[dict[str, Any]] = [
    {
        "key": "graphic",
        "title": "خدمات گرافیکی",
        "emoji": "🎨",
        "description": "طراحی هویت بصری، چاپی و محتوای تصویری کسب و کار شما.",
        "show_portfolio": True,
        "portfolio_text": PORTFOLIO_HINT,
        "items": [
            item(
                "logo",
                "طراحی لوگو",
                [
                    q("field", "حوزه کاری شما چیست؟"),
                    q(
                        "existing",
                        "لوگوی فعلی دارید؟",
                        "choice",
                        options=["لوگو دارم", "لوگو ندارم", "نیاز به بازطراحی دارم"],
                    ),
                    q(
                        "style",
                        "سبک مورد نظر شما",
                        "choice",
                        options=["مینیمال", "کلاسیک", "مدرن", "خلاقانه", "مشاوره می خواهم"],
                    ),
                    q("colors", "رنگ های مورد علاقه یا رنگ برند", required=False),
                    q(
                        "details",
                        "توضیحات تکمیلی درباره کسب و کار و مخاطب",
                        "long_text",
                        required=False,
                    ),
                ],
                description="لوگوی اختصاصی همراه با فایل های چاپی و دیجیتال.",
                show_portfolio=True,
            ),
            item(
                "business-card",
                "طراحی کارت ویزیت",
                [
                    q(
                        "orientation",
                        "کارت افقی باشد یا عمودی؟",
                        "choice",
                        options=["افقی", "عمودی", "مربعی", "مشاوره می خواهم"],
                    ),
                    q(
                        "print_type",
                        "چاپ معمولی لازم دارید یا ویژه؟",
                        "choice",
                        options=["معمولی", "ویژه (لمینت، طلاکوب و ...)", "فعلا فقط فایل می خواهم"],
                    ),
                    q("info", "چه اطلاعاتی روی کارت بیاید؟", "long_text"),
                    q("details", "توضیحات تکمیلی", "long_text", required=False),
                ],
                description="کارت ویزیت با فایل آماده چاپ.",
                show_portfolio=True,
            ),
            item(
                "catalog",
                "طراحی کاتالوگ و بروشور",
                [
                    q("pages", "تعداد صفحات کاتالوگ", "number", min_value=2, max_value=300),
                    q(
                        "type",
                        "کاتالوگ چاپی است یا دیجیتال؟",
                        "choice",
                        options=["چاپی", "دیجیتال", "هر دو"],
                    ),
                    q(
                        "content_ready",
                        "محتوا و تصاویر آماده است؟",
                        "choice",
                        options=["آماده است", "کمی آماده است", "آماده نیست"],
                    ),
                    q("details", "توضیحات تکمیلی", "long_text", required=False),
                ],
                description="کاتالوگ محصولات یا خدمات با صفحه آرایی حرفه ای.",
            ),
            item(
                "social-graphics",
                "طراحی پست و استوری شبکه های اجتماعی",
                [
                    q("count", "چند طرح لازم دارید؟", "number", min_value=1, max_value=200),
                    q(
                        "platform",
                        "برای کدام پلتفرم؟",
                        "choice",
                        options=["اینستاگرام", "تلگرام", "لینکدین", "چند پلتفرم"],
                    ),
                    q("details", "موضوع و توضیحات طرح ها", "long_text"),
                ],
                description="طرح های آماده انتشار با اندازه استاندارد هر پلتفرم.",
            ),
            item(
                "motion",
                "موشن گرافی و ویدیو",
                [
                    q("duration", "مدت ویدیو به ثانیه", "number", min_value=5, max_value=600),
                    q(
                        "usage",
                        "ویدیو کجا استفاده می شود؟",
                        "choice",
                        options=["اینستاگرام", "یوتیوب", "سایت", "تلویزیون و نمایشگر"],
                    ),
                    q(
                        "script",
                        "سناریو یا متن دارید؟",
                        "choice",
                        options=["بله", "نه، نیاز به نگارش دارم"],
                    ),
                    q("details", "توضیحات تکمیلی", "long_text", required=False),
                ],
                description="ویدیوی موشن گرافی با صداگذاری و زیرنویس.",
                show_portfolio=True,
            ),
            item(
                "banner",
                "بنر و تابلو تبلیغاتی",
                [
                    q(
                        "usage",
                        "بنر کجا نصب یا نمایش داده می شود؟",
                        "choice",
                        options=["فضای شهری", "فروشگاه", "سایت و شبکه اجتماعی", "نمایشگاه"],
                    ),
                    q("size", "ابعاد تقریبی", required=False),
                    q("details", "توضیحات تکمیلی", "long_text", required=False),
                ],
                description="طرح بنر با فایل آماده چاپ در ابعاد سفارشی.",
            ),
        ],
    },
    {
        "key": "web-design",
        "title": "طراحی سایت",
        "emoji": "🌐",
        "description": "طراحی و بازطراحی سایت با تمرکز بر سرعت، سئو و تجربه کاربری.",
        "show_portfolio": True,
        "portfolio_text": PORTFOLIO_HINT,
        "items": [
            item(
                "corporate",
                "سایت شرکتی",
                WEB_QUESTIONS,
                description="سایت معرفی شرکت و خدمات.",
                show_portfolio=True,
            ),
            item(
                "shop",
                "فروشگاه اینترنتی",
                WEB_QUESTIONS,
                description="فروشگاه با مدیریت محصولات و سفارش ها.",
                show_portfolio=True,
            ),
            item(
                "blog",
                "سایت خبری و وبلاگ",
                WEB_QUESTIONS,
                description="سایت محتوایی با مدیریت دسته بندی ها.",
            ),
            item(
                "landing",
                "لندینگ پیج",
                WEB_QUESTIONS,
                description="صفحه فرود برای کمپین و جذب سرنخ.",
                show_portfolio=True,
            ),
            item(
                "lms",
                "سایت آموزشی",
                WEB_QUESTIONS,
                description="سایت دوره آموزشی با دسترسی به محتوا.",
            ),
            item(
                "redesign",
                "بازطراحی سایت موجود",
                WEB_QUESTIONS,
                description="بهبود ظاهر و سرعت سایت فعلی.",
            ),
        ],
    },
    {
        "key": "app-design",
        "title": "طراحی اپلیکیشن",
        "emoji": "📱",
        "description": "اپلیکیشن اندروید و نسخه تحت وب مناسب آیفون.",
        "show_portfolio": True,
        "portfolio_text": PORTFOLIO_HINT,
        "items": [
            item(
                "android", "اپلیکیشن اندروید", APP_QUESTIONS, description="اپلیکیشن نیتیو اندروید."
            ),
            item(
                "pwa",
                "نسخه تحت وب (مناسب iOS)",
                APP_QUESTIONS,
                description="اپلیکیشن تحت وب که روی آیفون هم نصب می شود.",
            ),
            item(
                "both",
                "اندروید و تحت وب (هر دو)",
                APP_QUESTIONS,
                description="یک محصول با دو نسخه.",
            ),
            item(
                "shop",
                "اپلیکیشن فروشگاهی",
                APP_QUESTIONS,
                description="فروش محصولات فیزیکی و مجازی مثل دوره و فایل.",
                show_portfolio=True,
            ),
            item(
                "edu",
                "اپلیکیشن آموزشی",
                APP_QUESTIONS,
                description="ارائه دوره و محتوای آموزشی به کاربران.",
            ),
            item(
                "booking", "اپلیکیشن نوبت دهی", APP_QUESTIONS, description="رزرو و نوبت دهی آنلاین."
            ),
        ],
    },
    {
        "key": "content",
        "title": "تولید محتوا",
        "emoji": "✍️",
        "description": "مقاله سئو شده به زبان های مختلف برای سایت شما.",
        "show_portfolio": True,
        "portfolio_text": PORTFOLIO_HINT,
        "items": [
            item(
                "article-fa",
                "مقاله فارسی",
                CONTENT_QUESTIONS,
                description="مقاله فارسی سئو شده.",
                show_portfolio=True,
            ),
            item(
                "article-en",
                "مقاله انگلیسی",
                CONTENT_QUESTIONS,
                description="مقاله انگلیسی سئو شده.",
            ),
            item("article-ar", "مقاله عربی", CONTENT_QUESTIONS, description="مقاله عربی سئو شده."),
            item(
                "article-other",
                "مقاله به زبان دیگر",
                CONTENT_QUESTIONS,
                description="زبان درخواستی خود را بنویسید.",
            ),
        ],
    },
    {
        "key": "seo",
        "title": "خدمات سئو",
        "emoji": "📈",
        "description": "بهبود رتبه سایت در گوگل با بسته های قابل تنظیم.",
        "show_portfolio": True,
        "portfolio_text": PORTFOLIO_HINT,
        "items": [
            item(
                "seo-basic",
                "سئو پایه (گرید ۱)",
                [
                    q("site", "آدرس سایت"),
                    q("keywords", "کلیدواژه های اصلی", "long_text"),
                    q("competitors", "سایت رقبا (اختیاری)", required=False),
                    q("details", "هدف شما از سئو چیست؟", "long_text", required=False),
                ],
                description="بهینه سازی فنی پایه و سئوی داخلی صفحات.",
            ),
            item(
                "seo-pro",
                "سئو حرفه ای (گرید ۲)",
                [
                    q("site", "آدرس سایت"),
                    q("keywords", "کلیدواژه های اصلی", "long_text"),
                    q("competitors", "سایت رقبا (اختیاری)", required=False),
                    q("details", "هدف شما از سئو چیست؟", "long_text", required=False),
                ],
                description="سئوی فنی و محتوایی همراه با گزارش ماهانه.",
            ),
            item(
                "seo-enterprise",
                "سئو سازمانی (گرید ۳)",
                [
                    q("site", "آدرس سایت"),
                    q("keywords", "کلیدواژه های اصلی", "long_text"),
                    q("competitors", "سایت رقبا (اختیاری)", required=False),
                    q("details", "هدف شما از سئو چیست؟", "long_text", required=False),
                ],
                description="برنامه سئوی بلندمدت برای سایت های بزرگ.",
            ),
            item(
                "seo-local",
                "سئو محلی",
                [
                    q("site", "آدرس سایت یا نام کسب و کار"),
                    q("city", "شهر هدف"),
                    q("details", "توضیحات تکمیلی", "long_text", required=False),
                ],
                description="دیده شدن در جستجوهای محلی و نقشه گوگل.",
            ),
            item(
                "seo-consult",
                "مشاوره سئو",
                [
                    q("site", "آدرس سایت"),
                    q("question", "سوال یا مشکل اصلی شما چیست؟", "long_text"),
                ],
                description="بررسی سایت و ارائه نقشه راه.",
            ),
        ],
    },
]
