"""Storefront UI translations.

Source of truth for supported storefront languages is settings.json
`target_languages`. This module provides the user-facing strings for those
languages and helpers to resolve the active language from a request.
"""

from fastapi import Request


DEFAULT_LANGUAGE = "fr"

# Fallback when settings.json cannot be read. The real source of truth is
# settings.json `target_languages`; see load_supported_languages().
_FALLBACK_LANGUAGES = ["fr", "en", "es", "ar"]

_LANGUAGE_NAMES = {
    "fr": "Français",
    "en": "English",
    "es": "Español",
    "ar": "العربية",
}


def load_supported_languages() -> list[str]:
    """Read supported storefront languages from settings.json target_languages."""
    import json
    from pathlib import Path

    settings_path = Path(__file__).parent.parent / "settings.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            raw = data.get("target_languages", "")
            if isinstance(raw, str) and raw.strip():
                codes = [c.strip() for c in raw.split(",") if c.strip()]
                if codes:
                    return codes
        except (json.JSONDecodeError, OSError):
            pass
    return list(_FALLBACK_LANGUAGES)


SUPPORTED_LANGUAGES = load_supported_languages()

_STRINGS: dict[str, dict[str, str]] = {
    "fr": {
        "site_name": "StoryForge",
        "tagline": "Des livres personnalisés où votre enfant est le héros",
        "catalog_title": "Choisir une histoire",
        "catalog_subtitle": "Choisissez un conte, ajoutez le prénom et la photo de votre enfant, et nous créons un livre unique.",
        "preview_btn": "Aperçu",
        "personalize_btn": "Personnaliser",
        "back_to_stories": "← Choisir une autre histoire",
        "choose_another_story": "← Choisir une autre histoire",
        "pages_label": "{page_count} pages",
        "previous": "← Précédent",
        "next": "Suivant →",
        "page_indicator": "{current} / {total}",
        "preview_cta_text": "Cette histoire vous plaît ?",
        "personalize_book": "Personnaliser ce livre →",
        "empty_state_title": "Aucune histoire disponible",
        "empty_state_desc": "Revenez bientôt, de nouveaux contes arrivent.",
        "language_label": "Langue",
        "child_section_title": "1. Votre enfant",
        "child_name_label": "Prénom de l'enfant",
        "child_name_placeholder": "ex. Lina",
        "photo_label": "Photo",
        "photo2_label": "Deuxième photo (optionnelle, améliore la précision)",
        "preview_my_book": "Voir mon livre",
        "generating": "Génération en cours...",
        "preview_status": "Personnalisation de votre histoire, cela prend environ 30 secondes...",
        "order_section_title": "3. Commande",
        "email_label": "Votre email",
        "email_placeholder": "vous@exemple.com",
        "send_code": "Envoyer le code",
        "verify": "Vérifier",
        "code_placeholder": "Code à 6 chiffres",
        "continue_payment": "Continuer vers le paiement",
        "success_title_paid": "Votre livre est en préparation !",
        "success_title_pending": "Paiement en cours de confirmation",
        "success_title_default": "Merci pour votre commande !",
        "success_desc_paid": "Nous avons bien reçu la commande pour <strong>{child_name}</strong>. Un email de confirmation a été envoyé à <strong>{email}</strong>.",
        "success_desc_default": "Vous recevrez un email de confirmation sous peu.",
        "back_to_store": "← Retour à la boutique",
        "reference": "Référence",
        "book": "Livre",
        "amount": "Montant",
        "status": "Statut",
        "crafting_notice": "Nous fabriquons votre livre personnalisé à la main et vous l'enverrons par email sous 48 heures.",
    },
    "en": {
        "site_name": "StoryForge",
        "tagline": "Personalized storybooks starring your child",
        "catalog_title": "Choose a story",
        "catalog_subtitle": "Pick a tale, add your child's name and photo, and we craft a one-of-a-kind book.",
        "preview_btn": "Preview",
        "personalize_btn": "Personalize",
        "back_to_stories": "← Choose another story",
        "choose_another_story": "← Choose another story",
        "pages_label": "{page_count} pages",
        "previous": "← Previous",
        "next": "Next →",
        "page_indicator": "{current} / {total}",
        "preview_cta_text": "Like this story?",
        "personalize_book": "Personalize this book →",
        "empty_state_title": "No stories available",
        "empty_state_desc": "Check back soon — new tales are on the way.",
        "language_label": "Language",
        "child_section_title": "1. Your child",
        "child_name_label": "Child's first name",
        "child_name_placeholder": "e.g. Lina",
        "photo_label": "Photo",
        "photo2_label": "Second photo (optional, improves accuracy)",
        "preview_my_book": "Preview my book",
        "generating": "Generating...",
        "preview_status": "Personalizing your story, this takes about 30 seconds...",
        "order_section_title": "3. Order",
        "email_label": "Your email",
        "email_placeholder": "you@example.com",
        "send_code": "Send code",
        "verify": "Verify",
        "code_placeholder": "6-digit code",
        "continue_payment": "Continue to payment",
        "success_title_paid": "Your book is on its way!",
        "success_title_pending": "Payment confirmation pending",
        "success_title_default": "Thank you for your order!",
        "success_desc_paid": "We received your order for <strong>{child_name}</strong>. A confirmation has been sent to <strong>{email}</strong>.",
        "success_desc_default": "You'll receive a confirmation email shortly.",
        "back_to_store": "← Back to store",
        "reference": "Reference",
        "book": "Book",
        "amount": "Amount",
        "status": "Status",
        "crafting_notice": "We personally craft your personalized book and will email it to you within 48 hours.",
    },
    "es": {
        "site_name": "StoryForge",
        "tagline": "Cuentos personalizados donde tu hijo es el héroe",
        "catalog_title": "Elige un cuento",
        "catalog_subtitle": "Escoge un cuento, añade el nombre y la foto de tu hijo, y creamos un libro único.",
        "preview_btn": "Vista previa",
        "personalize_btn": "Personalizar",
        "back_to_stories": "← Elegir otro cuento",
        "choose_another_story": "← Elegir otro cuento",
        "pages_label": "{page_count} páginas",
        "previous": "← Anterior",
        "next": "Siguiente →",
        "page_indicator": "{current} / {total}",
        "preview_cta_text": "¿Te gusta esta historia?",
        "personalize_book": "Personalizar este libro →",
        "empty_state_title": "No hay cuentos disponibles",
        "empty_state_desc": "Vuelve pronto, nuevos cuentos están en camino.",
        "language_label": "Idioma",
        "child_section_title": "1. Tu hijo",
        "child_name_label": "Nombre del niño",
        "child_name_placeholder": "p. ej. Lina",
        "photo_label": "Foto",
        "photo2_label": "Segunda foto (opcional, mejora la precisión)",
        "preview_my_book": "Ver mi libro",
        "generating": "Generando...",
        "preview_status": "Personalizando tu historia, esto tarda unos 30 segundos...",
        "order_section_title": "3. Pedido",
        "email_label": "Tu correo",
        "email_placeholder": "tu@ejemplo.com",
        "send_code": "Enviar código",
        "verify": "Verificar",
        "code_placeholder": "Código de 6 dígitos",
        "continue_payment": "Continuar al pago",
        "success_title_paid": "¡Tu libro está en camino!",
        "success_title_pending": "Pago en proceso de confirmación",
        "success_title_default": "¡Gracias por tu pedido!",
        "success_desc_paid": "Hemos recibido el pedido para <strong>{child_name}</strong>. Se ha enviado una confirmación a <strong>{email}</strong>.",
        "success_desc_default": "Recibirás un email de confirmación en breve.",
        "back_to_store": "← Volver a la tienda",
        "reference": "Referencia",
        "book": "Libro",
        "amount": "Importe",
        "status": "Estado",
        "crafting_notice": "Elaboramos tu libro personalizado a mano y te lo enviaremos por email en un plazo de 48 horas.",
    },
    "ar": {
        "site_name": "StoryForge",
        "tagline": "قصص مخصصة يكون فيها طفلك البطل",
        "catalog_title": "اختر قصة",
        "catalog_subtitle": "اختر حكاية، أضف اسم طفلك وصورته، ونصنع لك كتابًا فريدًا.",
        "preview_btn": "معاينة",
        "personalize_btn": "تخصيص",
        "back_to_stories": "← اختيار قصة أخرى",
        "choose_another_story": "← اختيار قصة أخرى",
        "pages_label": "{page_count} صفحة",
        "previous": "← السابق",
        "next": "التالي →",
        "page_indicator": "{current} / {total}",
        "preview_cta_text": "أعجبتك هذه القصة؟",
        "personalize_book": "تخصيص هذا الكتاب →",
        "empty_state_title": "لا توجد قصص متاحة",
        "empty_state_desc": "عد قريبًا، قصص جديدة في الطريق.",
        "language_label": "اللغة",
        "child_section_title": "1. طفلك",
        "child_name_label": "اسم الطفل",
        "child_name_placeholder": "مثال: لينا",
        "photo_label": "الصورة",
        "photo2_label": "صورة ثانية (اختيارية، تحسن الدقة)",
        "preview_my_book": "عرض كتابي",
        "generating": "جاري التوليد...",
        "preview_status": "جاري تخصيص قصتك، يستغرق الأمر حوالي 30 ثانية...",
        "order_section_title": "3. الطلب",
        "email_label": "بريدك الإلكتروني",
        "email_placeholder": "you@example.com",
        "send_code": "إرسال الرمز",
        "verify": "تحقق",
        "code_placeholder": "رمز مكون من 6 أرقام",
        "continue_payment": "المتابعة إلى الدفع",
        "success_title_paid": "كتابك في الطريق!",
        "success_title_pending": "جاري تأكيد الدفع",
        "success_title_default": "شكرًا لطلبك!",
        "success_desc_paid": "استلمنا طلبك لـ <strong>{child_name}</strong>. تم إرسال تأكيد إلى <strong>{email}</strong>.",
        "success_desc_default": "ستتلقى رسالة تأكيد عبر البريد الإلكتروني قريبًا.",
        "back_to_store": "← العودة إلى المتجر",
        "reference": "المرجع",
        "book": "الكتاب",
        "amount": "المبلغ",
        "status": "الحالة",
        "crafting_notice": "نصنع كتابك المخصص يدويًا ونرسله إليك عبر البريد الإلكتروني خلال 48 ساعة.",
    },
}


def language_name(code: str) -> str:
    return _LANGUAGE_NAMES.get(code, code)


def supported_languages() -> list[str]:
    return list(SUPPORTED_LANGUAGES)


def get_strings(lang: str) -> dict[str, str]:
    """Return UI strings for a language, falling back to the default."""
    return _STRINGS.get(lang, _STRINGS[DEFAULT_LANGUAGE])


def resolve_language(request: Request) -> str:
    """Resolve storefront language from cookie, query param, or Accept-Language header.

    Falls back to DEFAULT_LANGUAGE if no supported language is found.
    """
    supported = load_supported_languages()

    # 1. explicit query param
    query_lang = (request.query_params.get("lang") or "").strip().lower()
    if query_lang in supported:
        return query_lang

    # 2. cookie
    cookie_lang = (request.cookies.get("sf_lang") or "").strip().lower()
    if cookie_lang in supported:
        return cookie_lang

    # 3. Accept-Language header
    accept = request.headers.get("accept-language", "")
    for part in accept.replace(";", ",").split(","):
        code = part.strip().split("-")[0].lower()
        if code in supported:
            return code

    return DEFAULT_LANGUAGE
