"""XMLs sinteticos (dados ficticios) que reproduzem os padroes de bug do corpus real.
NUNCA usar XML real do corpus (privacidade/LGPD) — estes sao fabricados."""

# NF-e multi-item COM IPI e ICMS-ST: total_produtos do ICMSTot (300) != 1o item (100);
# vNF (360) = 300 +10 +5 +2 -7 (desc) +30 (IPI) +20 (ST). Exercita B1 e B2.
NFE_MULTI_ITEM_IPI_ST = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
 <infNFe Id="NFe35250611222333000181550010000000011000000017">
  <ide><nNF>11</nNF><serie>1</serie><dhEmi>2026-03-01T10:00:00-03:00</dhEmi></ide>
  <emit><CNPJ>11222333000181</CNPJ><xNome>Fornecedor Sintetico Ltda</xNome></emit>
  <det nItem="1"><prod><xProd>ITEM A</xProd><NCM>61099000</NCM><CFOP>5101</CFOP><vProd>100.00</vProd></prod></det>
  <det nItem="2"><prod><xProd>ITEM B</xProd><NCM>61099000</NCM><CFOP>5101</CFOP><vProd>200.00</vProd></prod></det>
  <total><ICMSTot>
    <vProd>300.00</vProd><vFrete>10.00</vFrete><vSeg>5.00</vSeg>
    <vDesc>7.00</vDesc><vOutro>2.00</vOutro><vIPI>30.00</vIPI><vST>20.00</vST><vNF>360.00</vNF>
  </ICMSTot></total>
 </infNFe>
</NFe>"""

# NF-e multi-item SEM IPI/ST: total = soma dos itens (300). Isola o B1 (era BAIXA falso antes).
NFE_MULTI_ITEM_SIMPLES = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
 <infNFe Id="NFe35250611222333000181550010000000031000000034">
  <emit><CNPJ>11222333000181</CNPJ><xNome>Forn</xNome></emit>
  <det nItem="1"><prod><xProd>A</xProd><CFOP>5101</CFOP><vProd>100.00</vProd></prod></det>
  <det nItem="2"><prod><xProd>B</xProd><CFOP>5101</CFOP><vProd>200.00</vProd></prod></det>
  <total><ICMSTot><vProd>300.00</vProd><vFrete>0</vFrete><vSeg>0</vSeg><vDesc>0</vDesc>
    <vOutro>0</vOutro><vIPI>0</vIPI><vST>0</vST><vNF>300.00</vNF></ICMSTot></total>
 </infNFe>
</NFe>"""

# NF-e item unico (regressao: item == total, ja era ALTA, NAO pode quebrar).
NFE_ITEM_UNICO = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
 <infNFe Id="NFe35250611222333000181550010000000021000000028">
  <emit><CNPJ>11222333000181</CNPJ><xNome>Forn</xNome></emit>
  <det nItem="1"><prod><xProd>X</xProd><CFOP>5101</CFOP><vProd>500.00</vProd></prod></det>
  <total><ICMSTot><vProd>500.00</vProd><vFrete>0</vFrete><vSeg>0</vSeg><vDesc>0</vDesc>
    <vOutro>0</vOutro><vIPI>0</vIPI><vST>0</vST><vNF>500.00</vNF></ICMSTot></total>
 </infNFe>
</NFe>"""

# NF-e malformada SEM bloco <total><ICMSTot> (so item vProd): incompleta -> BAIXA (nao auto-aprovar).
NFE_SEM_ICMSTOT = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
 <infNFe Id="NFe35250611222333000181550010000000041000000041">
  <emit><CNPJ>11222333000181</CNPJ><xNome>Forn</xNome></emit>
  <det nItem="1"><prod><xProd>A</xProd><CFOP>5101</CFOP><vProd>100.00</vProd></prod></det>
 </infNFe>
</NFe>"""

# NFS-e nacional Simples (opSimpNac=3, ME/EPP): ISS no DAS, sem vISSQN -> NAO penalizar.
NFSE_NACIONAL_SIMPLES = """<?xml version="1.0" encoding="UTF-8"?>
<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">
 <infNFSe Id="NFS35001052212998017000169000000000000119">
  <nNFSe>119</nNFSe>
  <emit><CNPJ>11222333000181</CNPJ><xNome>Prestador Simples ME</xNome></emit>
  <DPS><infDPS><dhEmi>2026-01-30T12:00:00-03:00</dhEmi>
    <prest><CNPJ>11222333000181</CNPJ><regTrib><opSimpNac>3</opSimpNac></regTrib></prest>
    <serv><cServ><cTribNac>010101</cTribNac><xDescServ>Servico de exemplo</xDescServ></cServ></serv>
    <valores><vServPrest><vServ>3000.00</vServ></vServPrest></valores></infDPS></DPS>
  <valores><vLiq>3000.00</vLiq></valores>
 </infNFSe>
</NFSe>"""

# NFS-e nacional NAO optante (opSimpNac=1) sem ISS -> simples_nacional False (guarda o comportamento).
NFSE_NACIONAL_NAO_OPTANTE = NFSE_NACIONAL_SIMPLES.replace("<opSimpNac>3</opSimpNac>", "<opSimpNac>1</opSimpNac>")

# NFS-e nacional NAO optante (opSimpNac=1) mas IMUNE (tribISSQN=2, tpImunidade=3): ISS zero legitimo.
NFSE_NACIONAL_IMUNE = """<?xml version="1.0" encoding="UTF-8"?>
<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">
 <infNFSe Id="NFS35001052212998017000169000000000000777">
  <nNFSe>777</nNFSe>
  <emit><CNPJ>11222333000181</CNPJ><xNome>Prestador Imune</xNome></emit>
  <DPS><infDPS><dhEmi>2026-01-30T12:00:00-03:00</dhEmi>
    <prest><CNPJ>11222333000181</CNPJ><regTrib><opSimpNac>1</opSimpNac></regTrib></prest>
    <serv><cServ><cTribNac>010101</cTribNac><xDescServ>Servico imune</xDescServ></cServ></serv>
    <valores><vServPrest><vServ>12500.00</vServ></vServPrest>
      <trib><tribMun><tribISSQN>2</tribISSQN><tpImunidade>3</tpImunidade><tpRetISSQN>1</tpRetISSQN></tribMun></trib></valores></infDPS></DPS>
  <valores><vLiq>12500.00</vLiq></valores>
 </infNFSe>
</NFSe>"""

# guarda: NAO optante, TRIBUTAVEL (tribISSQN=1), SEM ISS -> deve seguir BAIXA (suspeito legitimo).
NFSE_NACIONAL_TRIBUTAVEL_SEM_ISS = NFSE_NACIONAL_IMUNE.replace("<tribISSQN>2</tribISSQN>", "<tribISSQN>1</tribISSQN>")
