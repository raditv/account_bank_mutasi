# -*- coding: utf-8 -*-

from openerp import models, fields, api
import socket
import httplib
import ssl
import urllib
import re
from httplib import (
	HTTPConnection,
	HTTPS_PORT,
	)
from sgmllib import SGMLParser
from datetime import date
from openerp.addons.account_bank_mutasi.units.common import (
	BaseBrowser,
	FormParser,
	open_file,
	to_float,
	to_date,
	)
class HTTPSConnection(HTTPConnection):
	"This class allows communication via SSL."
	default_port = HTTPS_PORT

	def __init__(self, host, port=None, key_file=None, cert_file=None,
			strict=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
			source_address=None):
		HTTPConnection.__init__(self, host, port, strict, timeout,
				source_address)
		self.key_file = key_file
		self.cert_file = cert_file

	def connect(self):
		"Connect to a host on a given (SSL) port."
		sock = socket.create_connection((self.host, self.port),
				self.timeout, self.source_address)
		if self._tunnel_host:
			self.sock = sock
			self._tunnel()
		# this is the only line we modified from the httplib.py file
		# we added the ssl_version variable
		self.sock = ssl.wrap_socket(sock, self.key_file, self.cert_file, ssl_version=ssl.PROTOCOL_TLSv1)

#now we override the one in httplib
httplib.HTTPSConnection = HTTPSConnection
# ssl_version corrections are done
class MutasiParser(SGMLParser):
	def __init__(self):
		SGMLParser.__init__(self)
		self.hasil = []
		self.baris = []
		self.data = []
		self.last_error = None

	def start_tr(self, attrs):
		pass

	def end_tr(self):
		if self.baris:
			self.hasil.append( self.baris )
		self.baris = []

	def start_td(self, attrs):
		pass

	def end_td(self):
		if self.data:
			self.baris.append(' '.join(self.data))
		self.data = []

	def handle_data(self, data):
		data = data.strip()
		if not data:
			return
		self.data.append(data)

	def get_clean_data(self):
		data = []
		for r in self.hasil:
			if ' '.join(r).find('TIDAK DAPAT DIPROSES') > -1:
				self.last_error = 'Tidak dapat diproses'
				return data
			if r[0] == 'Nomor Rekening':
				rekening = r[2].split()[0]
				continue
			if r[0].find('Saldo Awal') > -1:
				saldo = to_float(r[2])
				continue
			# Cari pola tanggal 10 karakter, 31/03/2009
			if len(r[0]) != 10:
				continue
			match = re.compile(r'([\d][\d])/[\d][\d]/[\d][\d][\d][\d]').search(r[0])
			if not match:
				continue
			d, m, y = map(lambda x: int(x), r[0].split('/'))
			tgl = date(y, m, d).isoformat()
			ket = r[1]
			debit = to_float(r[2])
			kredit = to_float(r[3])
			if r[2] == '0,00':
				nominal = to_float(r[3])
			else:
				nominal = - to_float(r[2])
			data.append([tgl, ket, nominal, debit, kredit])
		# Transaksi terbaru ada di paling atas
		data.reverse()
		#import pdb; pdb.set_trace()
		result = []
		for tgl, ket, nominal, debit, kredit in data:
			saldo += nominal
			#result.append([{'rekening':rekening, 'tanggal':tgl, 'reference': ket, 'debit': debit, 'kredit': kredit, 'saldo':saldo}])
			result.append([rekening, tgl, ket, debit, kredit, saldo])
		return result 


class Browser(BaseBrowser):
	def __init__(self, username, password, parser):
		super(Browser, self).__init__('https://ib.bankmandiri.co.id',
			username, password, parser) 

	def login(self):
		self.open_url('/retail/Login.do?action=form&lang=in_ID')
		self.br.select_form(nr=0)
		self.br['userID'] = self.username
		self.br['password'] = self.password
		self.info('Login %s' % self.username)
		resp = self.br.submit(name='image')
		content = resp.read()
		if re.compile('Maaf(.*) blokir').search(content):
			self.last_error = 'Telah diblokir'
		elif re.compile('Anda tidak dapat login').search(content):
			self.last_error = 'Tidak dapat login'
		else:
			return True

	def logout(self):
		self.open_url('/retail/Logout.do?action=result')

class MutasiBrowser(Browser):
	def __init__(self, username, password):
		Browser.__init__(self, username, password, MutasiParser)

	def browse(self, tgl, akhir):
		from_day = str(tgl.day)
		from_month = str(tgl.month)
		from_year = str(tgl.year)
		to_day = str(akhir.day)
		to_month = str(akhir.month)
		to_year = str(akhir.year)
		content = self.get_content('/retail/TrxHistoryInq.do?action=form')
		parser = FormParser()
		parser.feed(content)
		account_id = parser.selects['fromAccountID']['option'][0]
		self.br.select_form(nr=0)
		self.br['fromAccountID'] = [account_id] 
		self.br['fromDay'] = [from_day]
		self.br['fromMonth'] = [from_month]
		self.br['fromYear'] = [from_year]
		self.br['toDay'] = [to_day]
		self.br['toMonth'] = [to_month]
		self.br['toYear'] = [to_year]
		self.info('Account ID %s' % account_id)
		return self.br.submit()


class ResPartnerBank(models.Model):
	_inherit = "res.partner.bank"

	bank_user 		= fields.Char(string='E-Banking User')
	bank_password 	= fields.Char(string='E-Banking Password')
	bank_ebanking	= fields.Boolean(string='E-Banking Active')


class AccountJournal(models.Model):
	_inherit = "account.journal"

	bank_acc_user 		= fields.Char(related='bank_account_id.bank_user')
	bank_acc_password 	= fields.Char(related='bank_account_id.bank_password')
	bank_acc_ebanking 	= fields.Boolean(related='bank_account_id.bank_ebanking')
	mutasi_ids			= fields.One2many("account.bank.mutasi","journal_id","Mutasi",ondelete="cascade")


	@api.multi
	def open_action(self):
		action_name = self._context.get('action_name', False)
		if not action_name:
			if self.type == 'bank':
				action_name = 'action_bank_statement_tree'
			elif self.type == 'cash':
				action_name = 'action_view_bank_statement_tree'
			elif self.type == 'sale':
				action_name = 'action_invoice_tree1'
			elif self.type == 'purchase':
				action_name = 'action_invoice_tree2'
			else:
				action_name = 'action_move_journal_line'

		_journal_invoice_type_map = {
			('sale', None): 'out_invoice',
			('purchase', None): 'in_invoice',
			('sale', 'refund'): 'out_refund',
			('purchase', 'refund'): 'in_refund',
			('bank', None): 'bank',
			('cash', None): 'cash',
			('general', None): 'general',
		}
		invoice_type = _journal_invoice_type_map[(self.type, self._context.get('invoice_type'))]
		ctx = self._context.copy()
		ctx.pop('group_by', None)
		ctx.update({
			'journal_type': self.type,
			'default_journal_id': self.id,
			'search_default_journal_id': self.id,
		})
		ir_model_obj = self.pool['ir.model.data']
		if action_name == 'action_mutasi_list':
			model, action_id = ir_model_obj.get_object_reference(self._cr, self._uid, 'account_bank_mutasi', action_name)
		else:
			model, action_id = ir_model_obj.get_object_reference(self._cr, self._uid, 'account', action_name)
		action = self.pool[model].read(self._cr, self._uid, action_id, context=self._context)
		action['context'] = ctx
		action['domain'] = self._context.get('use_domain', [])
		return action


class MutasiBank(models.Model):
	_name = "account.bank.mutasi"

	journal_id	  = fields.Many2one("account.journal", "Journal", ondelete="cascade")
	name 		  = fields.Char(string="Reference")
	date_start	  = fields.Date(string="Start Date")
	date_end	  = fields.Date(string="To Date")
	debit 		  = fields.Float(string="Total Debit", compute="_total_balance")
	credit 		  = fields.Float(string="Total Credit", compute="_total_balance")
	transaksi_ids = fields.One2many("account.bank.mutasi.transaksi","mutasi_id","Transaksi",ondelete="cascade")


	@api.model
	def create(self, vals):
		if vals:
			vals.update({
				'name' : self.env['ir.sequence'].get('account.bank.mutasi')
				})
		return super(MutasiBank, self).create(vals)

	@api.one
	@api.depends('transaksi_ids')
	def _total_balance(self):
		if self.transaksi_ids:
			self.debit = sum(
				[nilai.debit for nilai in self.transaksi_ids])
			self.credit = sum(
				[nilai.credit for nilai in self.transaksi_ids])
		else:
			self.debit = 0.0
			self.credit = 0.0

	@api.multi
	def import_from_ebanking(self):
		new_lines = self.env['account.bank.mutasi.transaksi']
		grabber = MutasiBrowser(self.journal_id.bank_acc_user,self.journal_id.bank_acc_password)
		tgl = to_date(self.date_start)
		akhir = to_date(self.date_end)
		#import pdb; pdb.set_trace()
		data_mutasi = grabber.run(tgl,akhir)
		for rekening, tgl, ket, debit, kredit, saldo in data_mutasi:
			data = {
				'mutasi_id':self.id,
				'name': ket,
				'date': tgl,
				'debit': debit,
				'credit': kredit,
			}
			new_line = new_lines.new(data)
			new_lines += new_line
		self.transaksi_ids += new_lines
		return{}


class MutasiBankTransaksi(models.Model):
	_name = "account.bank.mutasi.transaksi"

	mutasi_id 	= fields.Many2one("account.bank.mutasi", "Mutasi", ondelete="cascade")
	name 	 	= fields.Char(string="Reference")
	date 		= fields.Date(string="Date")
	debit		= fields.Float(string="Debit")
	credit		= fields.Float(string="Credit")
