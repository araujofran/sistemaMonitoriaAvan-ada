from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class Detector:
    regex_id: str
    name: str
    description: str
    group: str
    pattern: str
    speaker: str = "ANY"
    criticality: str = "MEDIA"
    negations: tuple[str, ...] = ("não", "nunca", "nem", "jamais")
    exceptions: tuple[str, ...] = ()
    criteria: tuple[str, ...] = ()
    flags: int = re.IGNORECASE | re.UNICODE


def _d(i: int, name: str, group: str, pattern: str, speaker: str = "ANY", criteria: tuple[str, ...] = (), criticality: str = "MEDIA") -> Detector:
    return Detector(f"RGX_{group[:3].upper()}_{i:03d}", name, f"Detector de {name.replace('_', ' ')}", group, pattern, speaker, criticality, criteria=criteria)


DETECTORS = [
    _d(1,"protocolo","identification",r"\b(?:protocolo|n[uú]mero do atendimento)\s*[:º#-]?\s*(\d{6,20})\b"),
    _d(2,"cpf","identification",r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",criteria=("at_cx_intro2",)),
    _d(3,"cep","identification",r"\b\d{5}-?\d{3}\b",criteria=("at_cx_intro2",)),
    _d(4,"telefone","identification",r"(?<!\d)(?:\+?55\s*)?\(?\d{2}\)?\s*9?\d{4}[-\s]?\d{4}(?!\d)",criteria=("at_cx_intro2",)),
    _d(5,"email","identification",r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b",criteria=("at_cx_intro2",)),
    _d(6,"data","identification",r"\b(?:0?[1-9]|[12]\d|3[01])[/.-](?:0?[1-9]|1[0-2])[/.-](?:19|20)?\d{2}\b"),
    _d(7,"horario","identification",r"\b(?:[01]?\d|2[0-3])[:h][0-5]\d\b"),
    _d(8,"data_nascimento","identification",r"(?:nascimento|nasceu|nascida? em).{0,24}\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b",criteria=("at_cx_intro2",)),
    _d(9,"idade","identification",r"\b(?:tenho|idade)\s*(?:de\s*)?(\d{1,3})\s*anos\b"),
    _d(10,"agencia","identification",r"\bag[eê]ncia\s*[:º#-]?\s*\d{3,6}\b",criteria=("at_cx_intro2",)),
    _d(11,"conta","identification",r"\bconta\s*(?:corrente)?\s*[:º#-]?\s*\d{3,15}(?:-\d)?\b",criteria=("at_cx_intro2",)),
    _d(12,"rg","identification",r"\b(?:rg|identidade)\s*[:º#-]?\s*[\d.xX-]{5,14}\b",criteria=("at_cx_intro2",)),
    _d(13,"nome_mae","identification",r"(?:nome da (?:sua )?m[aã]e|sua m[aã]e se chama)",criteria=("at_cx_intro2",)),
    _d(14,"endereco","identification",r"\b(?:rua|avenida|av\.?|alameda|travessa)\s+[\wÀ-ÿ ]{3,}",criteria=("at_cx_intro2",)),
    _d(15,"saudacao","participants",r"\b(?:bom dia|boa tarde|boa noite|ol[aá]|seja bem[- ]vind[oa])\b","ATENDENTE",("at_cx_intro1","at_rel_cord3")),
    _d(16,"encerramento","participants",r"\b(?:agrade[çc]o o contato|tenha um bom dia|posso ajudar em algo mais|at[eé] logo)\b","ATENDENTE",("at_inad_compr5",)),
    _d(17,"identificacao_atendente","participants",r"\b(?:meu nome [eé]|quem fala [eé])\s+[A-ZÀ-Ý][a-zà-ÿ]+","ATENDENTE",("at_cx_intro1",)),
    _d(18,"identificacao_banco","participants",r"\b(?:banco|central de atendimento|financeira)\b","ATENDENTE",("at_cx_intro1",)),
    _d(19,"nome_cliente","participants",r"\b(?:meu nome [eé]|me chamo)\s+([A-ZÀ-Ý][a-zà-ÿ]+)","CLIENTE",("at_rel_cord1",)),
    _d(20,"tratamento_nome","participants",r"\b(?:senhor|senhora|sr\.?|sra\.?)\s+[A-ZÀ-Ý][a-zà-ÿ]+","ATENDENTE",("at_rel_cord1",)),
    _d(21,"cartao_consignado","products",r"\bcart[aã]o consignado\b"),
    _d(22,"cartao_credito","products",r"\bcart[aã]o (?:de )?cr[eé]dito\b"),
    _d(23,"emprestimo_consignado","products",r"\bempr[eé]stimo consignado\b"),
    _d(24,"emprestimo","products",r"\bempr[eé]stimo\b"),
    _d(25,"financiamento_veiculo","products",r"\bfinanciamento (?:de )?(?:ve[ií]culo|carro|moto)\b"),
    _d(26,"financiamento","products",r"\bfinanciamento\b"),
    _d(27,"conta_corrente","products",r"\bconta corrente\b"),
    _d(28,"boleto","products",r"\bboleto\b"),
    _d(29,"portabilidade","products",r"\bportabilidade\b"),
    _d(30,"renegociacao","products",r"\brenegocia[çc][aã]o\b"),
    _d(31,"refinanciamento","products",r"\brefinanciamento\b"),
    _d(32,"seguro","products",r"\bseguro\b"),
    _d(33,"pix","products",r"\bpix\b"),
    _d(34,"transferencia_produto","products",r"\btransfer[eê]ncia\b"),
    _d(35,"cobranca","products",r"\bcobran[çc]a\b"),
    _d(36,"quitacao","intent",r"\b(?:quita[çc][aã]o|quitar)\b"),
    _d(37,"segunda_via","intent",r"\bsegunda via\b"),
    _d(38,"cancelamento","intent",r"\b(?:quero cancelar|cancele|cancelamento|encerrar (?:o )?produto|n[aã]o quero mais)\b","CLIENTE"),
    _d(39,"reclamacao","intent",r"\b(?:quero reclamar|vou reclamar|reclama[çc][aã]o|absurdo|p[eé]ssimo atendimento)\b","CLIENTE"),
    _d(40,"contestacao","intent",r"\b(?:contesta[çc][aã]o|contestar|n[aã]o reconhe[çc]o|essa (?:compra|transa[çc][aã]o) n[aã]o [eé] minha)\b","CLIENTE"),
    _d(41,"desbloqueio","intent",r"\bdesbloque(?:ar|io)\b"),
    _d(42,"bloqueio","intent",r"\bbloque(?:ar|io)\b"),
    _d(43,"consulta","intent",r"\b(?:consultar|consulta|verificar)\b"),
    _d(44,"parcelamento","intent",r"\bparcelamento\b"),
    _d(45,"fraude","intent",r"\b(?:fraude|golpe|clonagem|clonado|invas[aã]o|roubo|furto)\b"),
    _d(46,"pagamento","intent",r"\bpagamento\b"),
    _d(47,"atualizacao_cadastral","intent",r"\b(?:atualiza[çc][aã]o|atualizar) cadastral\b"),
    _d(48,"por_favor","relationship",r"\bpor favor\b","ATENDENTE",("at_rel_cord3",)),
    _d(49,"agradecimento_atendente","relationship",r"\b(?:obrigad[oa]|agrade[çc]o)\b","ATENDENTE",("at_rel_cord3",)),
    _d(50,"desculpas","relationship",r"\b(?:desculp(?:a|e|as)|pe[çc]o desculpas|lamento|lamentamos)\b","ATENDENTE",("at_rel_cord2",)),
    _d(51,"acolhimento","relationship",r"\b(?:posso ajudar|vou ajudar|conte comigo|vamos verificar)\b","ATENDENTE",("at_rel_cord3",)),
    _d(52,"empatia","relationship",r"\b(?:compreendo|entendo (?:a sua|sua) situa[çc][aã]o|imagino como)\b","ATENDENTE",("at_rel_cord4",)),
    _d(53,"seguranca_fala","relationship",r"\b(?:vou verificar|consultei|confirmei|consta no sistema)\b","ATENDENTE",("at_rel_ling3",)),
    _d(54,"vicio_ne","language",r"(?<!\w)n[eé](?!\w)","ATENDENTE",("at_rel_ling2",)),
    _d(55,"vicio_ta","language",r"(?<!\w)t[aá](?!\w)","ATENDENTE",("at_rel_ling2",)),
    _d(56,"vicio_tipo_assim","language",r"\btipo assim\b","ATENDENTE",("at_rel_ling2",)),
    _d(57,"vicio_entendeu","language",r"\bentendeu\??\b","ATENDENTE",("at_rel_ling2",)),
    _d(58,"vicio_beleza","language",r"\bbeleza\??\b","ATENDENTE",("at_rel_ling2",)),
    _d(59,"gerundismo","language",r"\b(?:vou|iremos|vamos|estaremos)\s+estar\s+\w+(?:ando|endo|indo)\b","ATENDENTE",("at_rel_ling4",)),
    _d(60,"ofensiva","language",r"\b(?:idiota|burro|imbecil|droga|porcaria)\b","ATENDENTE",("at_rel_ling1","at_inad_compr6"),"ALTA"),
    _d(61,"resolucao_explicita","resolution",r"\b(?:resolvido|conclu[ií]do|realizado|j[aá] foi feito|est[aá] regularizado|foi enviado)\b","ATENDENTE",("at_cx_classif1","at_cx_classif3")),
    _d(62,"nao_resolucao","resolution",r"\b(?:n[aã]o consegui(?:mos)? ajudar|n[aã]o foi poss[ií]vel|n[aã]o consigo realizar|n[aã]o conseguimos resolver)\b","ATENDENTE",("at_cx_classif1","at_cx_classif3"),"ALTA"),
    _d(63,"recontato","resolution",r"\b(?:ligue novamente|retorne|entre em contato (?:novamente|amanh[aã])|volte a ligar|procure novamente)\b","ATENDENTE",("at_cx_classif1","at_cx_classif2")),
    _d(64,"transferencia_realizada","resolution",r"\b(?:vou|irei) transferir\b","ATENDENTE"),
    _d(65,"transferencia_negada","resolution",r"\bn[aã]o (?:vou|posso|consigo) transferir\b","ATENDENTE"),
    _d(66,"proximo_passo","resolution",r"\b(?:retorne|aguarde|ligue|acesse|compare[çc]a|envie|encaminhe|pr[oó]ximo passo)\b","ATENDENTE",("at_cx_classif2",)),
    _d(67,"prazo","resolution",r"\b(?:em at[eé] \d+ dias|\d+ dias [uú]teis|amanh[aã]|prazo)\b","ATENDENTE",("at_cx_classif2","at_inad_compr3")),
    _d(68,"mudanca_canal","ces",r"\b(?:acesse o aplicativo|entre no site|v[aá] [aà] ag[eê]ncia|fale com outro setor|envie por e-mail|whatsapp)\b","ATENDENTE",("ces1_canal",)),
    _d(69,"retrabalho","ces",r"\b(?:j[aá] liguei|novamente|de novo|outra vez|j[aá] entrei em contato|segunda vez|terceira vez|\d+ vezes)\b","CLIENTE",("ces2_retrabalho",)),
    _d(70,"friccao","friction",r"\b(?:n[aã]o entendi|explique novamente|muita dificuldade|n[aã]o funciona|erro|indispon[ií]vel|demora)\b","CLIENTE",("cx1_friccao",)),
    _d(71,"raiva","sentiment",r"\b(?:absurdo|revoltad[oa]|raiva|inadmiss[ií]vel)\b","CLIENTE"),
    _d(72,"frustracao","sentiment",r"\b(?:frustrad[oa]|decepcionad[oa]|cansad[oa] disso)\b","CLIENTE"),
    _d(73,"preocupacao","sentiment",r"\b(?:preocupad[oa]|com medo|receio)\b","CLIENTE"),
    _d(74,"agradecimento_cliente","sentiment",r"\b(?:obrigad[oa]|agrade[çc]o)\b","CLIENTE"),
    _d(75,"alivio","sentiment",r"\b(?:que al[ií]vio|ainda bem|fico tranquil[oa])\b","CLIENTE"),
    _d(76,"ameaca","sentiment",r"\b(?:vou processar|vou denunciar|meu advogado)\b","CLIENTE"),
    _d(77,"elogio_explicito","sentiment",r"\b(?:excelente atendimento|parab[eé]ns|voc[eê] me ajudou muito|[oó]timo atendimento)\b","CLIENTE",("inv_extra1",)),
    _d(78,"ouvidoria","risk",r"\bouvidoria\b","CLIENTE",(),"ALTA"),
    _d(79,"bacen","risk",r"\b(?:banco central|bacen)\b","CLIENTE",(),"ALTA"),
    _d(80,"procon","risk",r"\bprocon\b","CLIENTE",(),"ALTA"),
    _d(81,"consumidor_gov","risk",r"\bconsumidor\.?gov\b","CLIENTE",(),"ALTA"),
    _d(82,"judicial","risk",r"\b(?:advogad[oa]|processo|justi[çc]a|a[çc][aã]o judicial)\b","CLIENTE",(),"ALTA"),
    _d(83,"confirmacao_dado","security",r"\b(?:confirma|pode confirmar|qual [eé] o seu|informe)\b","ATENDENTE",("at_cx_intro2",)),
    _d(84,"validacao_entendimento","quality",r"\b(?:entendi que|s[oó] para confirmar|correto\?|[eé] isso mesmo\?)\b","ATENDENTE",("at_cx_compr4",)),
    _d(85,"pergunta_sondagem","quality",r"\b(?:o que aconteceu|desde quando|qual o motivo|pode me explicar|como ocorreu)\b","ATENDENTE",("at_cx_compr1",)),
    _d(86,"convite_pesquisa","compliance",r"\b(?:pesquisa de satisfa[çc][aã]o|avalie (?:o )?atendimento|responda [aà] pesquisa)\b","ATENDENTE",("at_inad_compr1",)),
    _d(87,"protocolo_informado","compliance",r"\b(?:seu protocolo [eé]|anote o protocolo)\b","ATENDENTE",("at_inad_compr2",)),
    _d(88,"alteracao_prazo","compliance",r"\b(?:prazo foi alterado|novo prazo|prorroga[çc][aã]o)\b","ATENDENTE",("at_inad_compr4",)),
    _d(89,"desligamento","compliance",r"\b(?:vou desligar|encerrar a liga[çc][aã]o)\b","ATENDENTE",("at_inad_compr5",)),
    _d(90,"prejuizo","compliance",r"\b(?:perdi dinheiro|causou preju[ií]zo|cobran[çc]a indevida|multa indevida)\b","CLIENTE",("at_inad_compr7",),"ALTA"),
    _d(91,"espera","operational",r"\b(?:aguarde um momento|permane[çc]a na linha|demorou muito)\b"),
    _d(92,"indisponibilidade","operational",r"\b(?:sistema indispon[ií]vel|fora do ar|indisponibilidade)\b","ATENDENTE"),
    _d(93,"erro_plataforma","operational",r"\b(?:erro no aplicativo|erro no sistema|aplicativo n[aã]o funciona)\b"),
    _d(94,"politica","operational",r"\b(?:pol[ií]tica do banco|n[aã]o [eé] permitido|regra do produto)\b","ATENDENTE"),
    _d(95,"correspondente","journey",r"\bcorrespondente banc[aá]rio\b"),
    _d(96,"agencia_canal","journey",r"\b(?:ag[eê]ncia|presencialmente)\b"),
    _d(97,"aplicativo_canal","journey",r"\b(?:aplicativo|app)\b"),
    _d(98,"site_canal","journey",r"\bsite\b"),
    _d(99,"whatsapp_canal","journey",r"\bwhats(?:app)?\b"),
    _d(100,"telefone_canal","journey",r"\b(?:telefone|central|liga[çc][aã]o)\b"),
]

assert 80 <= len(DETECTORS) <= 150
BY_NAME = {d.name: d for d in DETECTORS}

