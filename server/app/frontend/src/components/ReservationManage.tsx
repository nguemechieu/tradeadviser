import  { useEffect, useState } from "react";
import {
    Box,
    Typography,
    Button,
    Paper,
    Grid,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
} from "@mui/material";

import { toast } from "react-toastify";
import { axiosPrivate } from "../api/axios";


const ReservationManager = () => {
    const [reservations, setReservations] = useState([]);
    const [selectedReservation, setSelectedReservation] = useState(null);
    const [openDialog, setOpenDialog] = useState(false);
    const [editMode, setEditMode] = useState(false);

    const fetchReservations = async () => {
        try {
            const res = await axiosPrivate.get("/api/v3/reservations/my");
            setReservations(res.data);
        } catch (error) {
            toast.error("Failed to fetch reservations.");
        }
    };

    useEffect(() => {
        fetchReservations();
    }, []);

    const handleEdit = (reservation) => {
        setSelectedReservation(reservation);
        setEditMode(true);
        setOpenDialog(true);
    };

    const handleCancel = async (reservationId) => {
        if (!window.confirm("Are you sure? A cancellation fee may apply.")) return;

        try {
            await axiosPrivate.delete(`/api/v3/reservations/${reservationId}`);
            toast.success("Reservation cancelled (fee may apply).");
            fetchReservations();
        } catch (error) {
            toast.error("Cancellation failed.");
        }
    };

    const handleSave = async () => {
        try {
            await axiosPrivate.put(`/api/v3/reservations/${selectedReservation.id}`, selectedReservation);
            toast.success("Reservation updated.");
            setOpenDialog(false);
            fetchReservations();
        } catch (error) {
            toast.error("Update failed.");
        }
    };

    return (
        <Box sx={{ p: 4 }}>
            <Typography variant="h4" mb={2}>
                My Reservations
            </Typography>

            <Grid container spacing={3}>
                {reservations.map((res) => (
                    <Grid  key={res.id}>
                        <Paper sx={{ p: 3 }} elevation={4}>
                            <Typography variant="h6">{res.category}</Typography>
                            <Typography variant="body2">{res.date} @ {res.time}</Typography>
                            <Typography variant="body2">Notes: {res.notes}</Typography>
                            <Box mt={2}>
                                <Button variant="outlined" onClick={() => handleEdit(res)} sx={{ mr: 2 }}>Edit</Button>
                                <Button variant="contained" color="error" onClick={() => handleCancel(res.id)}>Cancel</Button>
                            </Box>
                        </Paper>
                    </Grid>
                ))}
            </Grid>

            <Dialog open={openDialog} onClose={() => setOpenDialog(false)} fullWidth maxWidth="sm">
                <DialogTitle>{editMode ? "Edit Reservation" : "View Reservation"}</DialogTitle>
                <DialogContent>
                    <TextField
                        fullWidth
                        margin="normal"
                        label="Category"
                        value={selectedReservation?.category || ""}
                        onChange={(e) => setSelectedReservation({ ...selectedReservation, category: e.target.value })}
                    />
                    <TextField
                        fullWidth
                        margin="normal"
                        type="date"
                        label="Date"
                        InputLabelProps={{ shrink: true }}
                        value={selectedReservation?.date || ""}
                        onChange={(e) => setSelectedReservation({ ...selectedReservation, date: e.target.value })}
                    />
                    <TextField
                        fullWidth
                        margin="normal"
                        type="time"
                        label="Time"
                        InputLabelProps={{ shrink: true }}
                        value={selectedReservation?.time || ""}
                        onChange={(e) => setSelectedReservation({ ...selectedReservation, time: e.target.value })}
                    />
                    <TextField
                        fullWidth
                        margin="normal"
                        label="Notes"
                        multiline
                        rows={3}
                        value={selectedReservation?.notes || ""}
                        onChange={(e) => setSelectedReservation({ ...selectedReservation, notes: e.target.value })}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
                    <Button onClick={handleSave} variant="contained">Save</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default ReservationManager;
