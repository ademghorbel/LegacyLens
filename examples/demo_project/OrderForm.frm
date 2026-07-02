VERSION 5.00
Begin VB.Form OrderForm
   Caption = "Order Entry"
End
Attribute VB_Name = "OrderForm"

Private Sub cmdSubmit_Click()
    Dim total As Currency
    total = CCur(txtQty.Text) * CCur(txtPrice.Text)
    If total > 1000 Then
        total = total * 0.95  ' bulk discount
    End If
    lblTotal.Caption = Format(total, "Currency")
End Sub

Private Function ValidateOrder() As Boolean
    ValidateOrder = Len(txtCustomer.Text) > 0 And IsNumeric(txtQty.Text)
End Function
