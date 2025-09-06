-- Criar banco de dados
CREATE DATABASE IF NOT EXISTS estoque_db;
USE estoque_db;

-- Criar tabela de produtos
CREATE TABLE produtos (
    codigo VARCHAR(20) PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    categoria VARCHAR(50),
    quantidade INT NOT NULL DEFAULT 0,
    preco DECIMAL(10,2) NOT NULL,
    descricao TEXT,
    fornecedor VARCHAR(100),
    estoque_minimo INT NOT NULL DEFAULT 5
);

-- Inserir registros de exemplo
INSERT INTO produtos (codigo, nome, categoria, quantidade, preco, descricao, fornecedor, estoque_minimo) VALUES
('P001', 'Notebook Lenovo', 'Eletrônicos', 15, 3500.00, 'Notebook Lenovo Ideapad 3, 8GB RAM, SSD 256GB', 'TechSupplier Ltda', 5),
('P002', 'Camiseta Polo', 'Vestuário', 40, 79.90, 'Camiseta polo algodão tamanho M', 'FashionWear', 10),
('P003', 'Smartphone Samsung A14', 'Eletrônicos', 8, 1200.00, 'Smartphone com 128GB armazenamento', 'MobileTech', 3),
('P004', 'Cadeira Gamer', 'Móveis', 5, 899.99, 'Cadeira gamer ergonômica preta e vermelha', 'OfficePlus', 2),
('P005', 'Fone de Ouvido JBL', 'Eletrônicos', 25, 199.90, 'Fone Bluetooth JBL Tune 510BT', 'SoundStore', 5);
