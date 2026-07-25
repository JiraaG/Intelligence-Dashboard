-- 016_add_new_categories.sql — Espansione delle tipologie primarie (da 10 a 15)

ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_primary_category_check;

ALTER TABLE articles ADD CONSTRAINT articles_primary_category_check CHECK (
    primary_category IN (
        'Nucleare',
        'Energia',
        'Infrastrutture',
        'Geopolitica',
        'Economia',
        'Tecnologia',
        'Spazio',
        'Ambiente',
        'Salute',
        'Sicurezza',
        'Intelligenza Artificiale',
        'Cybersecurity',
        'Finanza',
        'Difesa',
        'Materie Prime'
    )
);
