"""Fixtures sinteticas (dados ficticios) para captura de status/natureza (capture-only).

Cobrem: NF-e de DEVOLUCAO (natOp) -> sinaliza sem inverter; NF-e de VENDA normal
-> nao sinaliza; NFS-e PDF carimbada CANCELADA -> conferir + motivo + coluna.
"""

# NF-e de DEVOLUCAO (natOp) -> deve sinalizar devolucao + conferir (NAO inverter)
NFE_DEVOLUCAO = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
 <infNFe Id="NFe35250611222333000181550010000000091000000098">
  <ide><nNF>9</nNF><natOp>DEVOLUCAO DE MERCADORIA</natOp></ide>
  <emit><CNPJ>11222333000181</CNPJ><xNome>Forn</xNome></emit>
  <det nItem="1"><prod><xProd>X</xProd><CFOP>5202</CFOP><vProd>500.00</vProd></prod></det>
  <total><ICMSTot><vProd>500.00</vProd><vFrete>0</vFrete><vSeg>0</vSeg><vDesc>0</vDesc>
    <vOutro>0</vOutro><vIPI>0</vIPI><vST>0</vST><vNF>500.00</vNF></ICMSTot></total>
 </infNFe></NFe>"""

# NF-e de VENDA normal (natOp venda) -> NAO sinaliza, segue ALTA
NFE_VENDA = NFE_DEVOLUCAO.replace("DEVOLUCAO DE MERCADORIA", "VENDA DE MERCADORIA").replace("5202", "5101")

# dict PDF de NFS-e carimbada CANCELADA -> conferir + motivo CANCELADA
NFSE_PDF_CANCELADA = {"classe": "nfse", "cancelada": True, "campos": {
    "emitente_cnpj": {"valor": "11222333000181"}, "valor_servicos": {"valor": "1000,00"},
    "iss_valor": {"valor": "50,00"}, "iss_base": {"valor": "1000,00"}, "iss_aliquota": {"valor": "5,00"}}}
