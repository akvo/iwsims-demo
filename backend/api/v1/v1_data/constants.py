class DataApprovalStatus:
    pending = 1
    approved = 2
    rejected = 3

    FieldStr = {
        pending: "Pending",
        approved: "Approved",
        rejected: "Rejected",
    }


class FileActionTypes:
    added = 1
    changed = 2
    removed = 3

    FieldStr = {
        added: "Document added to the batch",
        changed: "Document has been changed",
        removed: "Document removed from the batch",
    }
