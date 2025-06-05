"""
Templates para geração de respostas automáticas
"""

RESPONSE_TEMPLATES = {
    'saudacoes': [
        "Olá, {nome}!",
        "Oi, {nome}!",
        "Olá!"
    ],
    'agradecimentos': [
        "Muito obrigada pelo seu comentário tão gentil!",
        "Agradeço imensamente suas palavras!",
        "Muito obrigada pelo seu feedback!",
        "Agradeço muito pelo seu comentário.",
        "Muito obrigada pelas palavras tão carinhosas!",
        "Agradeço pelo carinho e pela confiança!"
    ],
    'satisfacao': [
        "Fico feliz em saber que você se sentiu bem atendida.",
        "Fico muito contente em saber que o atendimento foi positivo para você.",
        "É muito gratificante saber que você ficou satisfeita com o atendimento.",
        "Fico feliz que tenha se sentido acolhida e confortável durante a consulta.",
        "Saber que você se sentiu segura e bem cuidada me deixa muito contente.",
        "Fico feliz em saber que consegui esclarecer suas dúvidas e proporcionar um atendimento atencioso."
    ],
    'qualidades_mencionadas': {
        'atenciosa': "Fico feliz que tenha percebido a atenção dedicada ao seu atendimento.",
        'educada': "Agradeço por reconhecer o cuidado e respeito no atendimento.",
        'explicar_detalhes': "Fico contente que minhas explicações tenham sido claras e detalhadas.",
        'profissional': "É gratificante saber que percebeu o profissionalismo no atendimento.",
        'pontual': "Prezo sempre pela pontualidade e atenção com cada paciente.",
        'competente': "Meu compromisso é sempre oferecer um atendimento de qualidade e baseado nas melhores práticas médicas.",
        'cuidadosa': "Estarei sempre aqui para cuidar com atenção e responsabilidade.",
        'eficiente': "Meu compromisso é sempre oferecer um cuidado eficiente e de excelência."
    },
    'disponibilidade': [
        "Estou sempre à disposição para o que precisar!",
        "Estarei à disposição sempre que precisar!",
        "Conte comigo sempre que precisar.",
        "Estou sempre à disposição para oferecer um cuidado atencioso e de qualidade.",
        "Estarei sempre aqui para cuidar de você com atenção e dedicação."
    ],
    'assinatura': "Atenciosamente,\nDra. Bruna Gomes"
}

QUALITY_KEYWORDS = {
    'atenciosa': ['atenciosa', 'atenção', 'atenta', 'atencioso'],
    'educada': ['educada', 'educado', 'gentil', 'simpática'],
    'explicar_detalhes': ['explica', 'explicou', 'detalhes', 'esclareceu'],
    'profissional': ['profissional', 'competente', 'qualificada'],
    'pontual': ['pontual', 'pontualidade'],
    'cuidadosa': ['cuidadosa', 'cuidado', 'humana'],
    'eficiente': ['eficiente', 'excelente', 'ótimo', 'ótima']
}