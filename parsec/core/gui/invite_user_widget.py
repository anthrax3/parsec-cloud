# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPLv3 2019 Scille SAS

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import QWidget, QApplication

from structlog import get_logger

from parsec.core.invite_claim import (
    InviteClaimTimeoutError,
    InviteClaimBackendOfflineError,
    InviteClaimError,
)

from parsec.api.protocol import InvitationType, HandshakeInvitedOperation, InvitationStatus
from parsec.core.types import BackendInvitationAddr

from parsec.core.backend_connection import (
    BackendNotAvailable,
    BackendConnectionError,
    backend_authenticated_cmds_factory,
)
from parsec.core.gui import desktop
from parsec.core.gui import validators
from parsec.core.gui.custom_dialogs import show_info, show_error, GreyedDialog
from parsec.core.gui.lang import translate as _
from parsec.core.gui.trio_thread import JobResultError, ThreadSafeQtSignal, QtToTrioJob
from parsec.core.gui.ui.invite_user_widget import Ui_InviteUserWidget
from parsec.core.gui.ui.user_invitation_widget import Ui_UserInvitationWidget


logger = get_logger()


async def _do_invite_user(device, config, email):
    async with backend_authenticated_cmds_factory(
        addr=device.organization_addr,
        device_id=device.device_id,
        signing_key=device.signing_key,
        keepalive=config.backend_connection_keepalive,
    ) as cmds:
        rep = await cmds.invite_new(type=InvitationType.USER, claimer_email=email, send_email=False)
        if rep["status"] != "ok":
            print(rep["status"])
            raise JobResultError(rep["status"])
        action_addr = BackendInvitationAddr.build(
            backend_addr=device.organization_addr,
            organization_id=device.organization_id,
            operation=HandshakeInvitedOperation.CLAIM_USER,
            token=rep["token"],
        )
        return action_addr


async def _do_list_invitations(device, config):
    async with backend_authenticated_cmds_factory(
        addr=device.organization_addr,
        device_id=device.device_id,
        signing_key=device.signing_key,
        keepalive=config.backend_connection_keepalive,
    ) as cmds:
        rep = await cmds.invite_list()
        if rep["status"] != "ok":
            raise JobResultError(rep["status"])
        return rep["invitations"]


class UserInvitationWidget(QWidget, Ui_UserInvitationWidget):
    cancel_invitation = pyqtSignal()

    def __init__(self, email, invite_addr, status):
        super().__init__()
        self.setupUi(self)
        STATUS_TEXTS = {
            InvitationStatus.READY: "Ready",
            InvitationStatus.IDLE: "Idle",
            InvitationStatus.DELETED: "Deleted",
        }
        self.email = email
        self.invite_addr = invite_addr
        self.label_email.clicked.connect(self.copy_field(self.label_status, self.email))
        self.label_invite_addr.clicked.connect(self.copy_field(self.label_status, self.invite_addr))
        font = QApplication.font()
        metrics = QFontMetrics(font)
        if metrics.horizontalAdvance(email) > 150:
            while metrics.horizontalAdvance(email + "...") > 150:
                email = email[: len(email) - 1]
            email += "..."
        self.label_email.setText(email)
        self.label_email.setToolTip(self.email)
        if metrics.horizontalAdvance(invite_addr) > 150:
            while metrics.horizontalAdvance(invite_addr + "...") > 150:
                invite_addr = invite_addr[: len(invite_addr) - 1]
            invite_addr += "..."
        self.label_invite_addr.setText(invite_addr)
        self.label_invite_addr.setToolTip(self.invite_addr)
        self.label_status.setText(STATUS_TEXTS[status])
        self.button_cancel.clicked.connect(self.cancel_invitation.emit)
        self.button_cancel.apply_style()

    def copy_field(self, widget, text):
        def _inner_copy_field(_unused):
            desktop.copy_to_clipboard(text)

        return _inner_copy_field


class InviteUserWidget(QWidget, Ui_InviteUserWidget):
    invite_user_success = pyqtSignal(QtToTrioJob)
    invite_user_error = pyqtSignal(QtToTrioJob)
    list_invitations_success = pyqtSignal(QtToTrioJob)
    list_invitations_error = pyqtSignal(QtToTrioJob)

    def __init__(self, core, jobs_ctx):
        super().__init__()
        self.setupUi(self)
        self.core = core
        self.dialog = None
        self.jobs_ctx = jobs_ctx
        self.list_invitations_success.connect(self._on_list_invitations_success)
        self.list_invitations_error.connect(self._on_list_invitations_error)
        self.invite_user_success.connect(self._on_invite_user_success)
        self.invite_user_error.connect(self._on_invite_user_error)
        self.button_invite_user.clicked.connect(self.invite_user)
        self.line_edit_user_email.textChanged.connect(self.check_infos)
        self.list_invitations()

    def list_invitations(self):
        self.jobs_ctx.submit_job(
            ThreadSafeQtSignal(self, "list_invitations_success", QtToTrioJob),
            ThreadSafeQtSignal(self, "list_invitations_error", QtToTrioJob),
            _do_list_invitations,
            device=self.core.device,
            config=self.core.config,
        )

    def invite_user(self):
        self.jobs_ctx.submit_job(
            ThreadSafeQtSignal(self, "invite_user_success", QtToTrioJob),
            ThreadSafeQtSignal(self, "invite_user_error", QtToTrioJob),
            _do_invite_user,
            device=self.core.device,
            config=self.core.config,
            email=self.line_edit_user_email.text(),
        )

    def _on_invite_user_success(self, job):
        print(job.ret)
        show_info(self, "User invited")
        self.list_invitations()

    def _on_invite_user_error(self, job):
        show_error(self, "Invite failed")
        print(job.status, job.exc)

    def _on_list_invitations_success(self, job):
        print(job.ret)
        self._clear_invitations_list()
        for invitation in job.ret:
            addr = BackendInvitationAddr.build(
                backend_addr=self.core.device.organization_addr,
                organization_id=self.core.device.organization_id,
                operation=HandshakeInvitedOperation.CLAIM_USER,
                token=invitation["token"],
            )
            w = UserInvitationWidget(invitation["claimer_email"], str(addr), invitation["status"])
            self.layout_invitations.insertWidget(0, w)

    def _on_list_invitations_error(self, job):
        show_error(self, "List failed")

    def _clear_invitations_list(self):
        while self.layout_invitations.count() > 1:
            item = self.layout_invitations.takeAt(0)
            if item:
                w = item.widget()
                self.layout_invitations.removeWidget(w)
                w.hide()
                w.setParent(None)

    def check_infos(self, text):
        if not text:
            self.button_invite_user.setDisabled(True)
        else:
            self.button_invite_user.setDisabled(False)

    @classmethod
    def exec_modal(cls, core, jobs_ctx, parent):
        w = cls(core=core, jobs_ctx=jobs_ctx)
        d = GreyedDialog(w, title=_("TEXT_INVITE_USER_TITLE"), parent=parent)
        w.dialog = d
        return d.exec_()
