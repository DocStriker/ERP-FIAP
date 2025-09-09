import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector

# CONFIGURAÇÃO DO MYSQL
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",# troque para seu usuário
    "password": "fiap",# troque para sua senha
    "database": "estoque_db"
}

class GerenciadorEstoque:
    def __init__(self):
        self.conn = None
        self.cur = None
        try:
            # Conecta ao MySQL
            self.conn = mysql.connector.connect(**DB_CONFIG)
            self.cur = self.conn.cursor()
            self.criar_banco_tabela()
        except mysql.connector.Error as err:
            messagebox.showerror("Erro de Conexão",
                                 f"Não foi possível conectar ao MySQL:\n{err}")

    def criar_banco_tabela(self):
        if not self.cur:
            return
        # Cria banco se não existir
        self.cur.execute("CREATE DATABASE IF NOT EXISTS estoque_db")
        self.cur.execute("USE estoque_db")
        # Cria tabela se não existir
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                codigo VARCHAR(20) PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                categoria VARCHAR(50),
                quantidade INT NOT NULL DEFAULT 0,
                preco DECIMAL(10,2) NOT NULL,
                descricao TEXT,
                fornecedor VARCHAR(100),
                estoque_minimo INT NOT NULL DEFAULT 5
            )
        """)
        self.conn.commit()

    def cadastrar_produto(self, produto):
        if not self.cur:
            return False
        try:
            self.cur.execute("""
                INSERT INTO produtos VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (produto["codigo"], produto["nome"], produto["categoria"],
                  produto["quantidade"], produto["preco"], produto["descricao"],
                  produto["fornecedor"], produto["estoque_minimo"]))
            self.conn.commit()
            return True
        except mysql.connector.IntegrityError:
            return False

    def listar_produtos(self):
        if not self.cur:
            return []
        self.cur.execute("SELECT * FROM produtos")
        return self.cur.fetchall()

    def atualizar_estoque(self, codigo, nova_qtd):
        if not self.cur:
            return False
        self.cur.execute("UPDATE produtos SET quantidade=%s WHERE codigo=%s", (nova_qtd, codigo))
        self.conn.commit()
        return self.cur.rowcount > 0

    def remover_estoque(self, codigo, qtd):
        if not self.cur:
            return False
        self.cur.execute("SELECT quantidade FROM produtos WHERE codigo=%s", (codigo,))
        res = self.cur.fetchone()
        if res and res[0] >= qtd:
            self.cur.execute("UPDATE produtos SET quantidade = quantidade - %s WHERE codigo=%s", (qtd, codigo))
            self.conn.commit()
            return True
        return False

    def adicionar_estoque(self, codigo, qtd):
        if not self.cur:
            return False
        self.cur.execute("UPDATE produtos SET quantidade = quantidade + %s WHERE codigo=%s", (qtd, codigo))
        self.conn.commit()
        return self.cur.rowcount > 0


# ================= INTERFACE GRAFICA =================
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Estoque (MySQL 8)")
        self.estoque = GerenciadorEstoque()

        if not self.estoque.cur:
            tk.Label(root, text="Não foi possível conectar ao banco MySQL.\nVerifique suas credenciais e se o MySQL está ativo.", fg="red").pack(pady=20)
            return

        # Formulário de cadastro
        frame = tk.Frame(root)
        frame.pack(pady=10)

        tk.Label(frame, text="Código").grid(row=0, column=0)
        tk.Label(frame, text="Nome").grid(row=0, column=1)
        tk.Label(frame, text="Categoria").grid(row=0, column=2)
        tk.Label(frame, text="Quantidade").grid(row=0, column=3)
        tk.Label(frame, text="Preço").grid(row=0, column=4)
        tk.Label(frame, text="Descrição").grid(row=0, column=5)
        tk.Label(frame, text="Fornecedor").grid(row=0, column=6)

        self.entries = [tk.Entry(frame) for _ in range(7)]
        for i, e in enumerate(self.entries):
            e.grid(row=1, column=i)

        tk.Button(frame, text="Cadastrar Produto", command=self.cadastrar).grid(row=1, column=7, padx=5)

        # Tabela de produtos
        self.tree = ttk.Treeview(root, columns=("codigo", "nome", "categoria", "quantidade", "preco", "fornecedor"), show="headings")
        for col in ("codigo", "nome", "categoria", "quantidade", "preco", "fornecedor"):
            self.tree.heading(col, text=col.capitalize())
        self.tree.pack(pady=10, fill="x")

        # Botões de ações
        btns = tk.Frame(root)
        btns.pack()
        tk.Button(btns, text="Adicionar Estoque", command=self.adicionar).grid(row=0, column=0, padx=5)
        tk.Button(btns, text="Remover Estoque", command=self.remover).grid(row=0, column=1, padx=5)
        tk.Button(btns, text="Atualizar Estoque", command=self.atualizar).grid(row=0, column=2, padx=5)

        self.carregar_tree()

    def carregar_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for p in self.estoque.listar_produtos():
            codigo, nome, categoria, quantidade, preco, descricao, fornecedor, estoque_min = p
            cor = "red" if quantidade <= estoque_min else ""
            self.tree.insert("", "end", values=(codigo, nome, categoria, quantidade, f"R${preco:.2f}", fornecedor), tags=(cor,))
        self.tree.tag_configure("red", background="#ffcccc")

    def cadastrar(self):
        try:
            codigo, nome, categoria, qtd, preco, descricao, fornecedor = [e.get() for e in self.entries]
            produto = {
                "codigo": codigo,
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
                messagebox.showerror("Erro", "Produto já existe!")
        except Exception:
            messagebox.showerror("Erro", "Preencha os campos corretamente!")

    def adicionar(self):
        item = self.tree.selection()
        if not item:
            return
        codigo = self.tree.item(item[0], "values")[0]
        qtd = self._ask_qtd("Adicionar")
        if qtd and self.estoque.adicionar_estoque(codigo, qtd):
            self.carregar_tree()

    def remover(self):
        item = self.tree.selection()
        if not item:
            return
        codigo = self.tree.item(item[0], "values")[0]
        qtd = self._ask_qtd("Remover")
        if qtd and self.estoque.remover_estoque(codigo, qtd):
            self.carregar_tree()

    def atualizar(self):
        item = self.tree.selection()
        if not item:
            return
        codigo = self.tree.item(item[0], "values")[0]
        qtd = self._ask_qtd("Nova quantidade")
        if qtd and self.estoque.atualizar_estoque(codigo, qtd):
            self.carregar_tree()

    def _ask_qtd(self, title):
        win = tk.Toplevel(self.root)
        win.title(title)
        tk.Label(win, text="Quantidade:").pack()
        entry = tk.Entry(win)
        entry.pack()
        result = {}

        def confirmar():
            try:
                result["qtd"] = int(entry.get())
                win.destroy()
            except:
                messagebox.showerror("Erro", "Digite um número válido!")
        tk.Button(win, text="OK", command=confirmar).pack()
        self.root.wait_window(win)
        return result.get("qtd")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
