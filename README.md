# Setup Discord — JORGE TURCO

Este bot cria automaticamente a estrutura inicial do servidor.

## Pelo celular
Você precisa executar/hospedar o bot em um ambiente que rode Python. O app do Discord sozinho não executa o ZIP.

## Configuração
1. Crie um bot no Discord Developer Portal.
2. Convide-o ao servidor com permissões para gerenciar canais e cargos.
3. Instale as dependências: `pip install -r requirements.txt`
4. Renomeie `.env.example` para `.env`.
5. Coloque o token e o ID do servidor no `.env`.
6. Execute `python bot.py`.
7. No Discord, use `/setup-servidor`.
8. Confirme no botão exibido.

O setup evita recriar categorias/canais/cargos que já existam pelo mesmo nome.
