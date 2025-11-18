import logging
from pathlib import Path
from typing import Callable, Optional, Tuple, Dict
from datetime import date, datetime
from collections import Counter
import sys # Import sys if not already present at the top

logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Evita adicionar múltiplos handlers se o módulo for recarregado
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO) # Ou logging.DEBUG para mais detalhes

class SpedFilterLogic:
    """
    Contém a lógica de negócios para filtrar um arquivo SPED
    por um intervalo de datas, usando os campos de data corretos
    para cada tipo de registro pai especificado.
    Atualiza Registro 0000 e recalcula contagens do Bloco 9.
    """

    def __init__(self):
        """
        Inicializa a lógica do filtro. Mapeia registros pais e seus índices de data.
        """
        logger.info("SpedFilterLogic (Date Filter) inicializado.")

        self.DOCUMENT_DATE_POSITIONS: Dict[str, int] = {
            # --- BLOCO C ---
            'C100': 11,  # <<< USA DT_E_S (Índice 11)
            'C300': 4,   # DT_DOC (Mantido como padrão)
            'C350': 10,  # DT_DOC (Mantido como padrão)
            'C405': 2,   # DT_DOC (Mantido como padrão)
            'C500': 12,  # <<< USA DT_DOC (Índice 12)
            'C600': 11,  # DT_DOC (Mantido como padrão)
            'C700': 11,  # DT_DOC (Mantido como padrão)

            # --- BLOCO D ---
            'D100': 12,  # <<< USA DT_A_P (Índice 12)
            'D300': 4,   # DT_DOC (Mantido como padrão)
            'D350': 10,  # DT_DOC (Mantido como padrão)
            'D400': 5,   # DT_DOC (Mantido como padrão)
            'D500': 11,  # <<< USA DT_DOC (Índice 11)
            'D600': 11,  # DT_DOC (Mantido como padrão)
            'D700': 10,  # <<< USA DT_DOC (Índice 10)
        }

        self.BLOCK_OPENERS: Dict[str, str] = {
            '0001': '0', 'C001': 'C', 'D001': 'D', 'E001': 'E',
            'G001': 'G', 'H001': 'H', 'K001': 'K',
            '1001': '1', '9001': '9',
        }
        self.BLOCK_CLOSERS: set[str] = {
            '0990', 'C990', 'D990', 'E990', 'G990', 'H990', 'K990', '1990', '9990'
        }

        # Blocos que contêm documentos a serem filtrados por data
        self.BLOCKS_TO_FILTER = {'C', 'D'}

    def _parse_sped_date(self, date_str: str) -> Optional[date]:
        """Converte uma data no formato SPED (ddmmyyyy) para um objeto date."""
        if not date_str or len(date_str) != 8:
            return None
        try:
            # Formato ddmmyyyy
            return date(
                int(date_str[4:8]),  # Ano (yyyy)
                int(date_str[2:4]),  # Mês (mm)
                int(date_str[0:2])   # Dia (dd)
            )
        except (ValueError, TypeError, IndexError):
            logger.warning(f"Data SPED malformada encontrada: '{date_str}'")
            return None

    def _format_date_sped(self, dt: date) -> str:
        """Formata um objeto date para o formato SPED (ddmmyyyy)."""
        return dt.strftime('%d%m%Y')

    def filter_sped_by_date(self,
                            input_path: Path | str,
                            output_path: Path | str,
                            start_date: date,
                            end_date: date,
                            encoding: str = 'latin-1',
                            progress_callback: Optional[Callable[[int], None]] = None
                            ) -> Tuple[bool, str]:
        """
        Filtra um arquivo SPED linha por linha com base em um intervalo de datas,
        usando os índices de data corretos especificados para C100, D100, C500, D500, D700.
        Atualiza Registro 0000 e recalcula contagens do Bloco 9.

        Args:
            input_path: Caminho para o arquivo SPED de entrada.
            output_path: Caminho para salvar o novo arquivo filtrado.
            start_date: Data de início (inclusiva).
            end_date: Data de fim (inclusiva).
            encoding: Codificação do arquivo (SPED é comumente 'latin-1').
            progress_callback: Função opcional para reportar o progresso (0-100).

        Returns:
            Uma tupla (sucesso: bool, mensagem: str)
        """

        logger.info(f"Iniciando filtro por data. Período: {start_date} a {end_date}")
        logger.info(f"Usando índices de data específicos: {self.DOCUMENT_DATE_POSITIONS}") # Log para confirmar
        logger.info(f"Entrada: {input_path}, Saída: {output_path}")

        lines_read = 0
        lines_written = 0
        record_counts = Counter() # Contador para registros escritos

        try:
            input_p = Path(input_path)
            output_p = Path(output_path)

            if not input_p.exists():
                raise FileNotFoundError(f"Arquivo de entrada não encontrado: {input_p}")

            total_lines = 0
            # 1. Contar linhas (para a barra de progresso)
            if progress_callback:
                logger.info("Contando linhas para barra de progresso...")
                try:
                    with input_p.open('r', encoding=encoding, errors='ignore') as f_count:
                        total_lines = sum(1 for _ in f_count)
                    logger.info(f"Total de linhas estimado: {total_lines}")
                except Exception as e:
                    logger.warning(f"Não foi possível contar as linhas: {e}. A barra de progresso pode não ser precisa.")
                    total_lines = 0 # Define como 0 se a contagem falhar

            with input_p.open('r', encoding=encoding, errors='ignore') as infile, \
                 output_p.open('w', encoding=encoding) as outfile:

                current_block = None         # Bloco atual (0, C, D, E...)
                keep_current_doc = False   # Flag para manter registros filhos
                first_line = True          # Flag para tratar o registro 0000

                for line in infile:
                    lines_read += 1
                    line_stripped = line.strip()

                    # Atualiza o progresso
                    if lines_read % 10000 == 0: # Atualiza a cada 10k linhas
                        logger.info(f"Processadas {lines_read} linhas...")
                        if progress_callback and total_lines > 0:
                            percent = min(int((lines_read / total_lines) * 100), 100) # Garante máximo de 100
                            progress_callback(percent)

                    # Validação básica da linha SPED
                    if not line_stripped.startswith('|') or not line_stripped.endswith('|') or len(line_stripped) < 7:
                        # logger.warning(f"Linha ignorada (formato inválido): {line_stripped[:100]}...") # Log opcional
                        continue

                    parts = line_stripped.split('|')
                    if len(parts) < 3: # Deve ter pelo menos |REG|CAMPO1|
                       continue

                    registro = parts[1]

                    if first_line and registro == '0000':
                        first_line = False
                        try:
                            parts[4] = self._format_date_sped(start_date) # DT_INI
                            parts[5] = self._format_date_sped(end_date)   # DT_FIN
                            modified_line = "|".join(parts) + "\n"
                            outfile.write(modified_line)
                            lines_written += 1
                            record_counts[registro] += 1
                            logger.info(f"Registro 0000 atualizado com datas: {parts[4]} a {parts[5]}")
                            # Define o bloco inicial como '0'
                            current_block = '0'
                        except IndexError:
                             logger.error("Registro 0000 não tem campos de data suficientes. Mantendo original.")
                             outfile.write(line) # Escreve original se falhar
                             lines_written += 1
                             record_counts[registro] += 1
                             current_block = '0' # Assume bloco 0
                        continue # Vai para a próxima linha

                    if registro in self.BLOCK_OPENERS:
                        current_block = self.BLOCK_OPENERS[registro]
                        logger.debug(f"Entrando no Bloco {current_block}") # Mudado para debug

                    line_to_write = None # Armazena a linha a ser escrita (se houver)

                    if current_block not in self.BLOCKS_TO_FILTER and current_block != '9':
                        line_to_write = line # Marca para escrever

                    # 2. Se estamos no Bloco C ou D:
                    elif current_block in self.BLOCKS_TO_FILTER:
                        # 2a. É um registro "Pai" de documento definido para filtro?
                        if registro in self.DOCUMENT_DATE_POSITIONS:
                            keep_current_doc = False # Reseta para este novo documento pai
                            date_to_check = None

                            try:
                                date_idx = self.DOCUMENT_DATE_POSITIONS[registro]

                                if len(parts) > date_idx and parts[date_idx]:
                                    date_str = parts[date_idx]
                                    date_to_check = self._parse_sped_date(date_str)
                                    logger.debug(f"Registro {registro}: Usando data do índice {date_idx} ('{date_str}') para checagem.")
                                else:
                                    # Se o campo específico estiver vazio ou faltando, não podemos filtrar por data
                                    logger.warning(f"Registro {registro} (linha {lines_read}): Campo de data no índice {date_idx} está vazio ou ausente. Documento descartado.")
                                    date_to_check = None # Garante que será descartado

                                # Verifica se a data lida (e válida) está no intervalo
                                if date_to_check and (start_date <= date_to_check <= end_date):
                                    line_to_write = line
                                    keep_current_doc = True # Marca para manter este doc e seus filhos
                                    logger.debug(f"Registro {registro} MANTIDO (Data: {date_to_check})")
                                else:
                                    if date_to_check: # Log apenas se a data foi lida mas está fora do intervalo
                                        logger.debug(f"Registro {registro} DESCARTADO (Data: {date_to_check} fora de {start_date}-{end_date})")
                              
                            except (IndexError, TypeError) as e:

                                logger.warning(f"Erro ao acessar data no índice {self.DOCUMENT_DATE_POSITIONS.get(registro, 'N/A')} para registro {registro}, descartando documento: {line_stripped[:100]}... Erro: {e}")
                                keep_current_doc = False

                        elif registro in self.BLOCK_OPENERS or registro in self.BLOCK_CLOSERS:
                            line_to_write = line # Sempre mantém aberturas/fechamentos de bloco
                            keep_current_doc = False # Reseta o flag ao fechar/abrir bloco

                        elif keep_current_doc:
                            line_to_write = line # Mantém o filho

                        else:
                            pass # Não faz nada (descarta a linha)

                    # Escreve a linha se ela foi marcada para escrita e conta o registro
                    if line_to_write:
                        outfile.write(line_to_write)
                        lines_written += 1
                        record_counts[registro] += 1

                logger.info("Recalculando e escrevendo Bloco 9...")
                if '9001' not in record_counts: # Garante que 9001 exista
                     record_counts['9001'] = 0
                record_counts['9001'] += 1 # Adiciona o próprio 9001
                outfile.write("|9001|0|\n") # Indicador de movimento (0 = com dados escritos)
                lines_written += 1
                record_counts['9900'] = len(record_counts) + 3

                # Adiciona contagens para 9990 e 9999 se ainda não existirem (improvável, mas seguro)
                if '9990' not in record_counts: record_counts['9990'] = 0
                if '9999' not in record_counts: record_counts['9999'] = 0
                record_counts['9990'] += 1
                record_counts['9999'] += 1


                
                
                bloco_9_line_count = 0
                for reg, count in sorted(record_counts.items()):
                     if reg not in ['9990','9999']:
                        line_9900 = f"|9900|{reg}|{count}|\n"
                        outfile.write(line_9900)
                        lines_written += 1
                        bloco_9_line_count += 1

                line_9990 = f"|9990|{bloco_9_line_count + 3}|\n"
                outfile.write(line_9990)
                lines_written += 1


                outfile.write(f"|9999|{lines_written + 1}|\n")
                lines_written += 1 # Conta a própria linha 9999

            # Garante que a barra chegue a 100% no final
            if progress_callback:
                progress_callback(100)

            logger.info(f"Filtro por data concluído. {lines_read} linhas lidas, {lines_written} linhas escritas.")
            # Mensagem final como antes
            return True, (f"Filtro por data concluído com sucesso!\n\n"
                          f"Linhas Lidas: {lines_read:,}\n"
                          f"Linhas Escritas: {lines_written:,}\n\n"
                          f"INFO: Datas no Reg 0000 atualizadas.\n"
                          f"INFO: Contagem Bloco 9 recalculada.\n\n"
                          f"ATENÇÃO: Apuração Bloco E NÃO recalculada.\n"
                          f"Arquivo para ANÁLISE ou importação de movimentos.")

        except FileNotFoundError as e:
            logger.error(f"Arquivo de entrada não encontrado: {e}")
            return False, f"Erro: Arquivo não encontrado:\n{e}"
        except IOError as e:
            logger.error(f"Erro de E/S ao processar arquivos: {e}")
            return False, f"Erro de Leitura/Escrita:\n{e}"
        except Exception as e:
            logger.exception(f"Erro inesperado durante o filtro: {e}") # Usar logger.exception para incluir traceback
            return False, f"Ocorreu um erro inesperado:\n{e}"