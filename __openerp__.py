# -*- coding: utf-8 -*-
{
    'name': "Account Bank Mutasi Indonesia",

    'summary': """
        Mutasi Rekening Bank
        Lihat mutasi rekening mandiri maksimal 2 bulan""",

    'description': """
        Mutasi Rekening Bank Indonesia
    """,

    'author': "Rachmat Aditiya",
    'website': "http://www.odoo.or.id",
    'category': 'Finance',
    'version': '0.1',
    'depends': ['base','account_accountant'],
    'data': [
        'views/account_bank_mutasi_inherit.xml',
        'views/account_bank_mutasi.xml',
        'views/account_journal_dashboard_view.xml',
        'sequence/sequence.xml'
    ],
}