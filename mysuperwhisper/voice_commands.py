"""
Voice commands processing for MySuperWhisper.
Handles text transformations based on spoken commands.
Supports multiple languages: French, English, Spanish.
"""

import re
from .config import log

# Multilingual patterns for newline commands
# Each tuple: (pattern, description for logging)
NEWLINE_PATTERNS = [
    # French
    (r'\bretour à la ligne\b', 'FR: retour à la ligne'),
    (r'\bretour a la ligne\b', 'FR: retour a la ligne'),
    (r'\bnouvelle ligne\b', 'FR: nouvelle ligne'),
    (r'\bà la ligne\b', 'FR: à la ligne'),
    (r'\ba la ligne\b', 'FR: a la ligne'),
    (r'\bsaut de ligne\b', 'FR: saut de ligne'),
    (r'\bligne suivante\b', 'FR: ligne suivante'),

    # English
    (r'\bnew line\b', 'EN: new line'),
    (r'\bnewline\b', 'EN: newline'),
    (r'\bline break\b', 'EN: line break'),
    (r'\bnext line\b', 'EN: next line'),
    (r'\bcarriage return\b', 'EN: carriage return'),

    # Spanish
    (r'\bnueva línea\b', 'ES: nueva línea'),
    (r'\bnueva linea\b', 'ES: nueva linea'),
    (r'\bsalto de línea\b', 'ES: salto de línea'),
    (r'\bsalto de linea\b', 'ES: salto de linea'),
    (r'\blínea siguiente\b', 'ES: línea siguiente'),
    (r'\blinea siguiente\b', 'ES: linea siguiente'),
]

# Multilingual keywords for validation (press Enter)
VALIDATE_KEYWORDS = {
    # French
    'valider', 'validé', 'valide', 'entrée', 'entrer',
    # English
    'enter', 'submit', 'validate', 'send', 'confirm',
    # Spanish
    'enviar', 'validar', 'confirmar', 'entrar',
}


# Common Whisper hallucinations or noise transcriptions to filter out
HALLUCINATIONS = [
    r'^beep[\.\!]*$',
    r'^merci d\'avoir regardé cette vidéo[\.\!]*$',
    r'^sous\-titres réalisés para la communauté d\'amara\.org$',
    r'^thank you for watching[\.\!]*$',
    r'^thanks for watching[\.\!]*$',
]


def process_voice_commands(text):
    """
    Process voice commands in transcribed text.

    Args:
        text: Raw transcribed text from Whisper

    Returns:
        tuple: (processed_text, should_validate)
            - processed_text: Text with commands replaced
            - should_validate: True if Enter key should be pressed
    """
    # Filter out common hallucinations/beeps
    for pattern in HALLUCINATIONS:
        if re.match(pattern, text.strip(), re.IGNORECASE):
            log(f"Filtered out hallucination: '{text}'")
            return "", False

    should_validate = False

    # Replace newline commands with actual newlines
    for pattern, description in NEWLINE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            log(f"Voice command found: '{description}' in '{text}'")
            text = re.sub(pattern, '\n', text, flags=re.IGNORECASE)

    # Clean up spaces around newlines
    if '\n' in text:
        # Remove spaces before and after newlines
        text = re.sub(r' *\n *', '\n', text)

    # Check if last word is a validation keyword
    words = text.strip().split()
    if words:
        last_word = words[-1].lower().rstrip('.,!?;:')
        if last_word in VALIDATE_KEYWORDS:
            # Remove the validation word from text
            text = ' '.join(words[:-1])
            should_validate = True
            log(f"Voice command detected: {words[-1]} -> Enter key")

    return text, should_validate
