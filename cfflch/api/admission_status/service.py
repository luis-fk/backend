import datetime


def check_admission_status(students_names: list[str]) -> None:
    previous_years = 5
    general_search_terms = [
        termo.strip()
        for termo in ["aprovado", "classificado", "convocado", "selecionado"]
    ]
    results_per_search = 5
    language_search = "pt-br"

    delay_google = 30
    delay_download = 5

    current_year = datetime.datetime.now().year
    anos_busca = [current_year - i for i in range(previous_years + 1)]

    resultados_encontrados_geral = []
    cabecalho_csv = [
        "Aluno",
        "Nome Normalizado Aluno",
        "Ano Encontrado",
        "Termo de Busca Usado",
        "URL da Lista",
        "Arquivo PDF Local",
    ]

    for nome_aluno_original in nomes_alunos_originais:
        nome_aluno_normalizado = normalizar_nome(nome_aluno_original)
        print(
            f"\n🎓 Processando aluno: {nome_aluno_original} (Normalizado: {nome_aluno_normalizado})"
        )

        aluno_encontrado_em_algum_pdf = False
        for ano in anos_busca:
            print(f"  🗓️  Ano: {ano}")

            query_usada, urls_pdf = buscar_pdfs_google(
                nome_aluno_original,
                nome_aluno_normalizado,
                ano,
                termos_busca_gerais,
                resultados_por_busca,
                idioma_busca,
                delay_google,
            )

            if not urls_pdf:
                print(
                    f'    ℹ️  Nenhum PDF encontrado para "{nome_aluno_original}" no ano {ano} com a query específica.'
                )
                continue

            for idx, url_pdf in enumerate(urls_pdf):
                caminho_pdf_local = baixar_pdf(
                    url_pdf,
                    pasta_pdfs,
                    nome_aluno_normalizado,
                    ano,
                    idx,
                    delay_download,
                )

                if caminho_pdf_local:
                    texto_pdf = extrair_texto_de_pdf(caminho_pdf_local)
                    if texto_pdf:
                        texto_pdf_normalizado = normalizar_nome(
                            texto_pdf
                        )  # Normalizar todo o texto do PDF
                        if nome_aluno_normalizado in texto_pdf_normalizado:
                            print(
                                f'    🎉 SUCESSO! Aluno "{nome_aluno_original}" ENCONTRADO no PDF: {caminho_pdf_local.name} (Origem: {url_pdf})'
                            )
                            resultado = [
                                nome_aluno_original,
                                nome_aluno_normalizado,
                                ano,
                                query_usada,
                                url_pdf,
                                str(caminho_pdf_local),
                            ]
                            resultados_encontrados_geral.append(resultado)
                            with open(
                                arquivo_resultados_nome,
                                "a",
                                newline="",
                                encoding="utf-8",
                            ) as f_csv:
                                writer = csv.writer(f_csv)
                                writer.writerow(resultado)
                            aluno_encontrado_em_algum_pdf = True
                        else:
                            print(
                                f'    ⚠️  Aluno "{nome_aluno_original}" NÃO encontrado no texto do PDF: {caminho_pdf_local.name}'
                            )
                    else:
                        print(
                            f"    ⚠️  Não foi possível extrair texto do PDF: {caminho_pdf_local.name}"
                        )
                else:
                    print(
                        f"    ⚠️  Falha no download ou processamento do PDF da URL: {url_pdf}"
                    )

            if not urls_pdf:  # Adiciona uma pausa mesmo se nenhum PDF for encontrado para esta query específica
                time.sleep(
                    delay_google / 2
                )  # Menor pausa se a busca não retornou nada.

        if not aluno_encontrado_em_algum_pdf:
            print(
                f'  😔 Aluno "{nome_aluno_original}" não encontrado em nenhuma lista nos anos pesquisados.'
            )
        print("-" * 40)

    print("\n🏁 Processo de busca finalizado!")
    if resultados_encontrados_geral:
        print(
            f"✅ {len(resultados_encontrados_geral)} ocorrência(s) de aluno(s) encontrada(s) e salvas em '{arquivo_resultados_nome}'."
        )
        print(f"📄 PDFs baixados estão na pasta: '{pasta_pdfs.resolve()}'")
    else:
        print("ℹ️ Nenhum aluno foi encontrado nas listas de acordo com os critérios.")
