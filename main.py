import tkinter as tk
from tkinter import messagebox
import sqlite3
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tkinter.ttk as ttk_native
from datetime import datetime
import json
import os

# ----------------- Utils -----------------
class Utils:
    def __init__(self):
        pass

    def centralizar(self, janela, largura, altura):
        janela.update_idletasks()
        largura_tela = janela.winfo_screenwidth()
        altura_tela = janela.winfo_screenheight()
        pos_x = (largura_tela // 2) - (largura // 2)
        pos_y = (altura_tela // 2) - (altura // 2)
        janela.geometry(f"{largura}x{altura}+{pos_x}+{pos_y}")

# ----------------- Gerenciador de Estoque / Vendas -----------------
class GerenciadorEstoque:
    def __init__(self, db_path="estoque.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()
        self.criar_banco_tabela()

    def criar_banco_tabela(self):
        # Tabela produtos
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                categoria TEXT,
                quantidade INTEGER NOT NULL DEFAULT 0,
                preco REAL NOT NULL,
                descricao TEXT,
                fornecedor TEXT,
                estoque_minimo INTEGER NOT NULL DEFAULT 5
            )
        """)

        # Tabela vendas
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS vendas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT DEFAULT (datetime('now','localtime')),
                total REAL,
                desconto REAL DEFAULT 0
            )
        """)

        # Itens da venda
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS venda_itens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venda_id INTEGER,
                produto_id INTEGER,
                quantidade INTEGER,
                preco_unit REAL,
                desconto_item REAL DEFAULT 0,
                FOREIGN KEY(venda_id) REFERENCES vendas(id),
                FOREIGN KEY(produto_id) REFERENCES produtos(id)
            )
        """)

        # Movimentações (adicionar/remover/venta)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS movimentacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER,
                tipo TEXT, -- 'add', 'remove', 'sale'
                quantidade INTEGER,
                data TEXT DEFAULT (datetime('now','localtime')),
                descricao TEXT,
                FOREIGN KEY(produto_id) REFERENCES produtos(id)
            )
        """)

        # Popula com alguns produtos iniciais se estiver vazio
        self.cur.execute("SELECT COUNT(*) FROM produtos")
        if self.cur.fetchone()[0] == 0:
            self.cur.executemany("""
                INSERT INTO produtos (nome, categoria, quantidade, preco, descricao, fornecedor, estoque_minimo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                ('Notebook Lenovo', 'Eletrônicos', 15, 3500.00, 'Notebook Lenovo Ideapad 3, 8GB RAM, SSD 256GB', 'TechSupplier Ltda', 5),
                ('Camiseta Polo', 'Vestuário', 40, 79.90, 'Camiseta polo algodão tamanho M', 'FashionWear', 10),
                ('Smartphone Samsung A14', 'Eletrônicos', 8, 1200.00, 'Smartphone com 128GB armazenamento', 'MobileTech', 3),
                ('Cadeira Gamer', 'Móveis', 5, 899.99, 'Cadeira gamer ergonômica preta e vermelha', 'OfficePlus', 2),
                ('Fone de Ouvido JBL', 'Eletrônicos', 25, 199.90, 'Fone Bluetooth JBL Tune 510BT', 'SoundStore', 5)
            ])
        self.conn.commit()

    # cadastrar produto (corrigido para especificar colunas)
    def cadastrar_produto(self, produto):
        try:
            self.cur.execute("""
                INSERT INTO produtos (nome, categoria, quantidade, preco, descricao, fornecedor, estoque_minimo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                produto["nome"], produto.get("categoria"),
                produto["quantidade"], produto["preco"],
                produto.get("descricao"), produto.get("fornecedor"),
                produto.get("estoque_minimo", 5)
            ))
            self.conn.commit()

            # registra movimentação de adição inicial
            produto_id = self.cur.lastrowid
            self.registrar_movimentacao(produto_id, 'add', produto["quantidade"], f'Cadastro inicial: {produto["nome"]}')
            return True
        except sqlite3.IntegrityError:
            return False

    def listar_produtos(self):
        self.cur.execute("SELECT * FROM produtos ORDER BY nome")
        return [dict(row) for row in self.cur.fetchall()]

    def obter_produto(self, produto_id):
        self.cur.execute("SELECT * FROM produtos WHERE id=?", (produto_id,))
        row = self.cur.fetchone()
        return dict(row) if row else None

    def atualizar_estoque(self, id, nova_qtd):
        self.cur.execute("SELECT quantidade FROM produtos WHERE id=?", (id,))
        res = self.cur.fetchone()
        if not res:
            return False
        self.cur.execute("UPDATE produtos SET quantidade = ? WHERE id = ?", (int(nova_qtd), id))
        self.conn.commit()
        # registra movimentação (tipo 'set' com descrição)
        self.registrar_movimentacao(id, 'set', int(nova_qtd), f'Atualização direta para {nova_qtd}')
        return True

    def remover_estoque(self, id, qtd):
        self.cur.execute("SELECT quantidade FROM produtos WHERE id=?", (id,))
        res = self.cur.fetchone()
        if res and res[0] >= qtd:
            self.cur.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE id=?", (qtd, id))
            self.conn.commit()
            self.registrar_movimentacao(id, 'remove', qtd, 'Remoção manual')
            return True
        return False

    def adicionar_estoque(self, id, qtd):
        self.cur.execute("UPDATE produtos SET quantidade = quantidade + ? WHERE id=?", (qtd, id))
        self.conn.commit()
        if self.cur.rowcount > 0:
            self.registrar_movimentacao(id, 'add', qtd, 'Adição manual')
            return True
        return False

    # registra movimentação no histórico
    def registrar_movimentacao(self, produto_id, tipo, quantidade, descricao=None):
        self.cur.execute("""
            INSERT INTO movimentacoes (produto_id, tipo, quantidade, descricao)
            VALUES (?, ?, ?, ?)
        """, (produto_id, tipo, quantidade, descricao))
        self.conn.commit()

    # registrar venda: items = [ {produto_id, quantidade, desconto_item (opcional)} ], desconto_total (opcional)
    def registrar_venda(self, items, desconto_total=0.0):
        # validar estoque
        for it in items:
            pid = int(it["produto_id"])
            qtd = int(it["quantidade"])
            self.cur.execute("SELECT quantidade, preco FROM produtos WHERE id=?", (pid,))
            row = self.cur.fetchone()
            if not row:
                raise ValueError(f"Produto {pid} não encontrado")
            if row["quantidade"] < qtd:
                raise ValueError(f"Estoque insuficiente para produto {pid} ({row['quantidade']} disponível)")

        # calcula total
        total_bruto = 0.0
        for it in items:
            pid = int(it["produto_id"])
            qtd = int(it["quantidade"])
            self.cur.execute("SELECT preco FROM produtos WHERE id=?", (pid,))
            preco = float(self.cur.fetchone()["preco"])
            desconto_item = float(it.get("desconto_item", 0.0))
            total_bruto += (preco * qtd) - desconto_item

        total_final = total_bruto - float(desconto_total)

        # cria venda
        self.cur.execute("INSERT INTO vendas (total, desconto) VALUES (?, ?)", (total_final, desconto_total))
        venda_id = self.cur.lastrowid

        # inserir itens, reduzir estoque, movimentar
        for it in items:
            pid = int(it["produto_id"])
            qtd = int(it["quantidade"])
            self.cur.execute("SELECT preco FROM produtos WHERE id=?", (pid,))
            preco = float(self.cur.fetchone()["preco"])
            desconto_item = float(it.get("desconto_item", 0.0))
            self.cur.execute("""
                INSERT INTO venda_itens (venda_id, produto_id, quantidade, preco_unit, desconto_item)
                VALUES (?, ?, ?, ?, ?)
            """, (venda_id, pid, qtd, preco, desconto_item))
            # reduzir estoque
            self.cur.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE id=?", (qtd, pid))
            # registrar movimentação tipo 'sale'
            self.registrar_movimentacao(pid, 'sale', qtd, f'Venda #{venda_id}')

        self.conn.commit()
        return venda_id, total_final

    # Relatórios
    def relatorio_vendas(self):
        self.cur.execute("SELECT * FROM vendas ORDER BY data DESC")
        vendas = [dict(r) for r in self.cur.fetchall()]
        # pegar itens de cada venda
        for v in vendas:
            self.cur.execute("SELECT vi.*, p.nome FROM venda_itens vi JOIN produtos p ON vi.produto_id = p.id WHERE vi.venda_id=?", (v["id"],))
            v["itens"] = [dict(i) for i in self.cur.fetchall()]
        return vendas

    def relatorio_estoque(self):
        self.cur.execute("SELECT * FROM produtos ORDER BY nome")
        return [dict(r) for r in self.cur.fetchall()]

    def historico_movimentacoes(self):
        self.cur.execute("""
            SELECT m.*, p.nome as produto_nome FROM movimentacoes m
            LEFT JOIN produtos p ON m.produto_id = p.id
            ORDER BY m.data DESC
        """)
        return [dict(r) for r in self.cur.fetchall()]

# ----------------- Interface Principal (com Vendas e Relatórios) -----------------
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Estoque e Vendas")
        self.estoque = GerenciadorEstoque()

        # Frame principal: formulário de cadastro
        frame = tk.Frame(root)
        frame.pack(pady=10, fill="x")

        labels = ["Nome", "Categoria", "Quantidade", "Preço", "Descrição", "Fornecedor"]
        for i, text in enumerate(labels):
            tk.Label(frame, text=text).grid(row=0, column=i)
        self.entries = [tk.Entry(frame) for _ in range(len(labels))]
        for i, e in enumerate(self.entries):
            e.grid(row=1, column=i, padx=5)
        tk.Button(frame, text="Cadastrar Produto", command=self.cadastrar).grid(row=1, column=len(labels), padx=5)

        # Treeview de produtos
        self.tree = ttk_native.Treeview(root, columns=("id", "nome", "categoria", "quantidade", "preco", "fornecedor"), show="headings", height=10)
        for col in ("id", "nome", "categoria", "quantidade", "preco", "fornecedor"):
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, anchor="center")
        self.tree.pack(pady=10, padx=10, fill="x")
        self.tree.tag_configure("red", background="#ffcccc")

        # Botões ações
        btns = tk.Frame(root)
        btns.pack()
        tk.Button(btns, text="Adicionar Estoque", command=self.adicionar).grid(row=0, column=0, padx=5)
        tk.Button(btns, text="Remover Estoque", command=self.remover).grid(row=0, column=1, padx=5)
        tk.Button(btns, text="Atualizar Estoque", command=self.atualizar).grid(row=0, column=2, padx=5)
        tk.Button(btns, text="Abrir Vendas", command=self.abrir_vendas).grid(row=0, column=3, padx=5)
        tk.Button(btns, text="Relatórios", command=self.abrir_relatorios).grid(row=0, column=4, padx=5)

        self.carregar_tree()

    def carregar_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for p in self.estoque.listar_produtos():
            id = p["id"]
            nome = p["nome"]
            categoria = p["categoria"]
            quantidade = p["quantidade"]
            preco = p["preco"]
            fornecedor = p["fornecedor"]
            estoque_min = p["estoque_minimo"]
            cor = "red" if quantidade <= estoque_min else ""
            self.tree.insert("", "end", values=(id, nome, categoria, quantidade, f"R${preco:.2f}", fornecedor), tags=(cor,))

    def cadastrar(self):
        try:
            nome, categoria, qtd, preco, descricao, fornecedor = [e.get() for e in self.entries]
            produto = {
                "nome": nome,
                "categoria": categoria,
                "quantidade": int(qtd),
                "preco": float(preco),
                "descricao": descricao,
                "fornecedor": fornecedor,
                "estoque_minimo": 5
            }
            if self.estoque.cadastrar_produto(produto):
                messagebox.showinfo("Sucesso", "Produto cadastrado!")
                self.carregar_tree()
            else:
                messagebox.showerror("Erro", "Não foi possível cadastrar o produto.")
        except Exception as ex:
            messagebox.showerror("Erro", f"Preencha os campos corretamente!\n{ex}")

    def adicionar(self):
        item = self.tree.selection()
        if not item:
            messagebox.showwarning("Atenção", "Selecione um produto")
            return
        id = int(self.tree.item(item[0], "values")[0])
        qtd = self._ask_qtd("Adicionar")
        if qtd and self.estoque.adicionar_estoque(id, qtd):
            self.carregar_tree()

    def remover(self):
        item = self.tree.selection()
        if not item:
            messagebox.showwarning("Atenção", "Selecione um produto")
            return
        id = int(self.tree.item(item[0], "values")[0])
        qtd = self._ask_qtd("Remover")
        if qtd and self.estoque.remover_estoque(id, qtd):
            self.carregar_tree()

    def atualizar(self):
        item = self.tree.selection()
        if not item:
            messagebox.showwarning("Atenção", "Selecione um produto")
            return
        id = int(self.tree.item(item[0], "values")[0])
        qtd = self._ask_qtd("Nova quantidade")
        if qtd is not None and self.estoque.atualizar_estoque(id, qtd):
            self.carregar_tree()

    def _ask_qtd(self, title):
        win = tk.Toplevel(self.root)
        win.attributes('-topmost', True)
        Utils().centralizar(win, 300, 100)
        win.title(title)
        tk.Label(win, text="Quantidade:").pack()
        entry = tk.Entry(win, width=10)
        entry.pack(pady=5)
        result = {}

        def confirmar():
            try:
                result["qtd"] = int(entry.get())
                win.destroy()
            except:
                messagebox.showerror("Erro", "Digite um número válido!", parent=win)
        tk.Button(win, text="OK", command=confirmar).pack(pady=5)
        self.root.wait_window(win)
        return result.get("qtd")

    # ----------------- VENDAS -----------------
    def abrir_vendas(self):
        VendaWindow(self.root, self.estoque, self.carregar_tree)

    # ----------------- RELATÓRIOS -----------------
    def abrir_relatorios(self):
        RelatoriosWindow(self.root, self.estoque)

# ----------------- Janela de Vendas -----------------
class VendaWindow:
    def __init__(self, parent, estoque: GerenciadorEstoque, atualizar_callback=None):
        self.parent = parent
        self.estoque = estoque
        self.atualizar_callback = atualizar_callback

        self.win = tk.Toplevel(parent)
        self.win.title("Vendas")
        self.win.attributes('-topmost', True)
        Utils().centralizar(self.win, 1500, 500)

        # Lista de produtos
        left = tk.Frame(self.win)
        left.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        tk.Label(left, text="Produtos").pack()
        self.tree_prod = ttk_native.Treeview(left, columns=("id", "nome", "qtd", "preco"), show="headings", height=12)
        for c in ("id", "nome", "qtd", "preco"):
            self.tree_prod.heading(c, text=c.capitalize())
            self.tree_prod.column(c, anchor="center")
        self.tree_prod.pack(fill="both", expand=True)
        self.carregar_produtos()

        # Controls para adicionar ao carrinho
        ctl = tk.Frame(left)
        ctl.pack(pady=5)
        tk.Label(ctl, text="Quantidade:").grid(row=0, column=0)
        self.entry_qtd = tk.Entry(ctl, width=6)
        self.entry_qtd.grid(row=0, column=1, padx=5)
        tk.Label(ctl, text="Desconto por item:").grid(row=0, column=2)
        self.entry_desc_item = tk.Entry(ctl, width=6)
        self.entry_desc_item.grid(row=0, column=3, padx=5)
        tk.Button(ctl, text="Adicionar ao Carrinho", command=self.adicionar_carrinho).grid(row=0, column=4, padx=5)

        # Carrinho
        right = tk.Frame(self.win)
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        tk.Label(right, text="Carrinho").pack()
        self.listbox_cart = tk.Listbox(right, width=50, height=12)
        self.listbox_cart.pack()
        self.cart = []  # items: dicts {produto_id, nome, quantidade, preco_unit, desconto_item}

        # descontos e total
        bottom = tk.Frame(right)
        bottom.pack(pady=10, fill="x")
        tk.Label(bottom, text="Desconto total:").grid(row=0, column=0)
        self.entry_desc_total = tk.Entry(bottom, width=8)
        self.entry_desc_total.grid(row=0, column=1, padx=5)
        tk.Button(bottom, text="Remover item selecionado", command=self.remover_item_cart).grid(row=0, column=2, padx=5)
        tk.Button(bottom, text="Finalizar Venda", command=self.finalizar_venda).grid(row=0, column=3, padx=5)

    def carregar_produtos(self):
        for i in self.tree_prod.get_children():
            self.tree_prod.delete(i)
        for p in self.estoque.listar_produtos():
            self.tree_prod.insert("", "end", values=(p["id"], p["nome"], p["quantidade"], f"R${p['preco']:.2f}"))

    def adicionar_carrinho(self):
        sel = self.tree_prod.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um produto")
            return
        produto_id = int(self.tree_prod.item(sel[0], "values")[0])
        nome = self.tree_prod.item(sel[0], "values")[1]
        try:
            qtd = int(self.entry_qtd.get())
        except:
            messagebox.showerror("Erro", "Quantidade inválida")
            return
        try:
            desconto_item = float(self.entry_desc_item.get()) if self.entry_desc_item.get() else 0.0
        except:
            messagebox.showerror("Erro", "Desconto inválido")
            return

        # verificar estoque
        prod = self.estoque.obter_produto(produto_id)
        if prod is None:
            messagebox.showerror("Erro", "Produto não encontrado")
            return
        if prod["quantidade"] < qtd:
            messagebox.showerror("Erro", f"Estoque insuficiente ({prod['quantidade']} disponível)")
            return

        self.cart.append({
            "produto_id": produto_id,
            "nome": nome,
            "quantidade": qtd,
            "preco_unit": float(prod["preco"]),
            "desconto_item": desconto_item
        })
        self._refresh_cart_list()

    def _refresh_cart_list(self):
        self.listbox_cart.delete(0, tk.END)
        for it in self.cart:
            line = f"{it['nome']} x{it['quantidade']} - R${it['preco_unit']:.2f} (-{it['desconto_item']:.2f})"
            self.listbox_cart.insert(tk.END, line)

    def remover_item_cart(self):
        sel = self.listbox_cart.curselection()
        if not sel:
            return
        idx = sel[0]
        del self.cart[idx]
        self._refresh_cart_list()

    def finalizar_venda(self):
        if not self.cart:
            messagebox.showwarning("Carrinho vazio", "Adicione itens ao carrinho antes de finalizar")
            return
        try:
            desconto_total = float(self.entry_desc_total.get()) if self.entry_desc_total.get() else 0.0
        except:
            messagebox.showerror("Erro", "Desconto total inválido")
            return

        # preparar items para registrar venda
        items_payload = []
        for it in self.cart:
            items_payload.append({
                "produto_id": it["produto_id"],
                "quantidade": it["quantidade"],
                "desconto_item": it.get("desconto_item", 0.0)
            })

        try:
            venda_id, total = self.estoque.registrar_venda(items_payload, desconto_total)
        except ValueError as e:
            messagebox.showerror("Erro na venda", str(e))
            return

        # gerar recibo (texto) e mostrar
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        recibo_lines = [f"RECIBO DE VENDA #{venda_id}", f"Data: {now}", "-"*40]
        total_bruto = 0.0
        for it in self.cart:
            subtotal = it['preco_unit'] * it['quantidade'] - it.get('desconto_item', 0.0)
            recibo_lines.append(f"{it['nome']} x{it['quantidade']}  R${it['preco_unit']:.2f}  Sub: R${subtotal:.2f}")
            total_bruto += subtotal
        recibo_lines.append("-"*40)
        recibo_lines.append(f"Total bruto: R${total_bruto:.2f}")
        recibo_lines.append(f"Desconto total aplicado: R${desconto_total:.2f}")
        recibo_lines.append(f"Total final: R${total:.2f}")

        recibo_text = "\n".join(recibo_lines)

        # Mostrar recibo em nova janela com opção de salvar
        self.mostrar_recibo(venda_id, recibo_text)

        # limpar carrinho e recarregar produtos/estoque
        self.cart.clear()
        self._refresh_cart_list()
        self.carregar_produtos()
        if self.atualizar_callback:
            self.atualizar_callback()

    def mostrar_recibo(self, venda_id, texto):
        w = tk.Toplevel(self.win)
        w.title(f"Recibo #{venda_id}")
        Utils().centralizar(w, 400, 400)
        txt = tk.Text(w, wrap="word")
        txt.insert("1.0", texto)
        txt.config(state="disabled")
        txt.pack(expand=True, fill="both")
        btns = tk.Frame(w)
        btns.pack(pady=5)
        def salvar():
            filename = f"recibo_venda_{venda_id}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(texto)
            messagebox.showinfo("Salvo", f"Recibo salvo em {os.path.abspath(filename)}")
        tk.Button(btns, text="Salvar Recibo (TXT)", command=salvar).pack(side="left", padx=5)
        tk.Button(btns, text="Fechar", command=w.destroy).pack(side="left", padx=5)

# ----------------- Janela de Relatórios -----------------
class RelatoriosWindow:
    def __init__(self, parent, estoque: GerenciadorEstoque):
        self.parent = parent
        self.estoque = estoque
        self.win = tk.Toplevel(parent)
        self.win.title("Relatórios")
        Utils().centralizar(self.win, 900, 600)

        # Tabs simples com 3 relatórios
        nb = ttk_native.Notebook(self.win)
        nb.pack(fill="both", expand=True)

        # Vendas
        tab_vendas = tk.Frame(nb)
        nb.add(tab_vendas, text="Relatório de Vendas")
        self.tree_vendas = ttk_native.Treeview(tab_vendas, columns=("id","data","total","desconto"), show="headings", height=10)
        for c in ("id","data","total","desconto"):
            self.tree_vendas.heading(c, text=c.capitalize())
        self.tree_vendas.pack(fill="both", expand=True)
        tk.Button(tab_vendas, text="Carregar Vendas", command=self.carregar_vendas).pack(pady=5)
        tk.Button(tab_vendas, text="Visualizar Itens da Venda Selecionada", command=self.visualizar_itens_venda).pack(pady=5)

        # Estoque
        tab_estoque = tk.Frame(nb)
        nb.add(tab_estoque, text="Relatório de Estoque")
        self.tree_estoque = ttk_native.Treeview(tab_estoque, columns=("id","nome","qtd","preco","min"), show="headings", height=12)
        for c in ("id","nome","qtd","preco","min"):
            self.tree_estoque.heading(c, text=c.capitalize())
        self.tree_estoque.pack(fill="both", expand=True)
        tk.Button(tab_estoque, text="Carregar Estoque", command=self.carregar_estoque).pack(pady=5)

        # Histórico
        tab_hist = tk.Frame(nb)
        nb.add(tab_hist, text="Histórico Movimentações")
        self.tree_hist = ttk_native.Treeview(tab_hist, columns=("data","produto","tipo","qtd","descricao"), show="headings", height=12)
        for c in ("data","produto","tipo","qtd","descricao"):
            self.tree_hist.heading(c, text=c.capitalize())
        self.tree_hist.pack(fill="both", expand=True)
        tk.Button(tab_hist, text="Carregar Histórico", command=self.carregar_hist).pack(pady=5)

    def carregar_vendas(self):
        for i in self.tree_vendas.get_children():
            self.tree_vendas.delete(i)
        vendas = self.estoque.relatorio_vendas()
        for v in vendas:
            self.tree_vendas.insert("", "end", values=(v["id"], v["data"], f"R${v['total']:.2f}", f"R${v['desconto']:.2f}"))

    def visualizar_itens_venda(self):
        sel = self.tree_vendas.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione uma venda")
            return
        venda_id = int(self.tree_vendas.item(sel[0], "values")[0])
        # pegar itens
        self.estoque.cur.execute("SELECT vi.*, p.nome FROM venda_itens vi JOIN produtos p ON vi.produto_id = p.id WHERE vi.venda_id=?", (venda_id,))
        itens = [dict(r) for r in self.estoque.cur.fetchall()]
        txt = "\n".join([f"{it['nome']} x{it['quantidade']}  R${it['preco_unit']:.2f} (-{it['desconto_item']:.2f})" for it in itens])
        messagebox.showinfo(f"Itens Venda #{venda_id}", txt or "Sem itens")

    def carregar_estoque(self):
        for i in self.tree_estoque.get_children():
            self.tree_estoque.delete(i)
        produtos = self.estoque.relatorio_estoque()
        for p in produtos:
            self.tree_estoque.insert("", "end", values=(p["id"], p["nome"], p["quantidade"], f"R${p['preco']:.2f}", p["estoque_minimo"]))

    def carregar_hist(self):
        for i in self.tree_hist.get_children():
            self.tree_hist.delete(i)
        movs = self.estoque.historico_movimentacoes()
        for m in movs:
            self.tree_hist.insert("", "end", values=(m["data"], m.get("produto_nome") or "-", m["tipo"], m["quantidade"], m["descricao"]))

# ----------------- Execução -----------------
if __name__ == "__main__":
    root = ttk.Window(themename="darkly")
    app = App(root)
    Utils().centralizar(root, 1000, 600)
    root.mainloop()
